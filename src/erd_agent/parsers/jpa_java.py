from __future__ import annotations
from pathlib import Path
import re
import javalang

from erd_agent.model import Schema, Column, Ref
from erd_agent.parsers.base import Parser

def camel_to_snake(name: str) -> str:
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()

JAVA_TYPE_MAP = {
    "String": "varchar",
    "int": "int",
    "Integer": "int",
    "long": "bigint",
    "Long": "bigint",
    "boolean": "boolean",
    "Boolean": "boolean",
    "LocalDate": "date",
    "LocalDateTime": "timestamp",
    "Date": "datetime",
    "BigDecimal": "decimal",
    "UUID": "uuid",
}

COLLECTION_TYPES = {"List", "Set", "Collection", "Iterable"}

class JPAJavaParser(Parser):
    def can_parse(self, path: Path, text: str) -> bool:
        # 스캐너가 이미 @Entity 중심으로 후보를 만들어주지만,
        # 안전하게 여기서도 @Entity 확인
        return path.suffix.lower() == ".java" and "@Entity" in text

    def parse(self, path: Path, text: str, schema: Schema) -> None:
        try:
            tree = javalang.parse.parse(text)
        except Exception:
            return

        for t in getattr(tree, "types", []) or []:
            if not hasattr(t, "annotations"):
                continue

            ann_names = {a.name for a in (t.annotations or [])}

            # ✅ 엔티티 판별은 @Entity로만
            if "Entity" not in ann_names:
                continue

            table_name = self._resolve_table_name(t)
            table = schema.ensure_table(table_name)

            for field in getattr(t, "fields", []) or []:
                anns = {a.name: a for a in (field.annotations or [])}
                raw_type = self._simple_type(field.type)

                for declarator in field.declarators:
                    var_name = declarator.name

                    # ---- 관계 처리 ----
                    if "ManyToOne" in anns or "OneToOne" in anns:
                        join_col = self._join_column_name(field)
                        fk_col_name = join_col or f"{camel_to_snake(var_name)}_id"

                        if fk_col_name not in table.columns:
                            table.columns[fk_col_name] = Column(
                                name=fk_col_name,
                                db_type="bigint",
                                nullable=True
                            )

                        parent_table = camel_to_snake(raw_type)
                        schema.refs.append(Ref(
                            child_table=table_name,
                            child_column=fk_col_name,
                            parent_table=parent_table,
                            parent_column="id",
                            rel=">"  # many-to-one 기준 [3](https://docs.oracle.com/en/java/javase/24/docs/api/java.base/java/lang/classfile/AnnotationElement.html)[4](https://jastadd.cs.lth.se/releases/extendj/8.0.1/doc/org/extendj/ast/ElementValuePair.html)
                        ))
                        continue

                    if "ManyToMany" in anns:
                        jt = self._join_table(field)
                        if jt:
                            join_table, join_col, inv_col = jt
                            jt_table = schema.ensure_table(join_table)

                            if join_col not in jt_table.columns:
                                jt_table.columns[join_col] = Column(join_col, "bigint", nullable=False)
                            if inv_col not in jt_table.columns:
                                jt_table.columns[inv_col] = Column(inv_col, "bigint", nullable=False)

                            schema.refs.append(Ref(join_table, join_col, table_name, "id", ">"))
                            schema.refs.append(Ref(join_table, inv_col, camel_to_snake(raw_type), "id", ">"))
                        continue

                    if "OneToMany" in anns:
                        # 양방향 추론은 오탐 위험이 커서 기본 스킵(향후 확장 포인트)
                        continue

                    # ---- 일반 컬럼 처리 ----
                    col = Column(
                        name=camel_to_snake(var_name),
                        db_type=JAVA_TYPE_MAP.get(raw_type, "varchar"),
                    )

                    if "Column" in anns:
                        self._apply_column_annotation(col, anns["Column"])

                    if "Id" in anns:
                        col.pk = True
                        col.nullable = False

                    if "GeneratedValue" in anns:
                        col.increment = True  # DB 자동생성 의미 [5](https://developers.openai.com/cookbook/examples/azure/chat)[6](https://coderivers.org/blog/azure-openai-python/)

                    if "Enumerated" in anns:
                        col.db_type = "varchar"

                    table.columns[col.name] = col

    def _simple_type(self, t) -> str:
        try:
            name = t.name
            if name in COLLECTION_TYPES and getattr(t, "arguments", None):
                arg0 = t.arguments[0]
                inner = getattr(arg0, "type", None)
                if inner is not None and getattr(inner, "name", None):
                    return inner.name
            return name
        except Exception:
            return "String"

    def _resolve_table_name(self, class_decl) -> str:
        """
        - 엔티티 이름: @Entity(name=...)가 있으면 반영 가능 [1](https://docs.dbdiagram.io/dbml/)
        - 테이블 이름: @Table(name=...)가 있으면 최우선, 없으면 엔티티명/클래스명 기반 [1](https://docs.dbdiagram.io/dbml/)[2](https://github.com/openai/openai-python/blob/main/examples/azure.py)
        - 스키마: @Table(schema=...)가 있으면 schema.table로 생성 (DBML 지원) [4](https://jastadd.cs.lth.se/releases/extendj/8.0.1/doc/org/extendj/ast/ElementValuePair.html)
        """
        entity_name = class_decl.name
        table_name = None
        schema_name = None

        for a in (class_decl.annotations or []):
            if a.name == "Entity":
                n = self._ann_kv(a, "name")
                if n:
                    entity_name = n
            elif a.name == "Table":
                table_name = self._ann_kv(a, "name")
                schema_name = self._ann_kv(a, "schema")

        base = table_name or camel_to_snake(entity_name)
        if schema_name:
            return f"{schema_name}.{base}"
        return base

    def _apply_column_annotation(self, col: Column, ann) -> None:
        name = self._ann_kv(ann, "name")
        if name:
            col.name = name

        nullable = self._ann_kv(ann, "nullable")
        if nullable is not None:
            col.nullable = (str(nullable).lower() != "false")

        unique = self._ann_kv(ann, "unique")
        if unique is not None:
            col.unique = (str(unique).lower() == "true")

        length = self._ann_kv(ann, "length")
        if length and col.db_type.startswith("varchar"):
            col.db_type = f"varchar({length})"

    def _join_column_name(self, field) -> str | None:
        for a in (field.annotations or []):
            if a.name == "JoinColumn":
                return self._ann_kv(a, "name")
        return None

    def _join_table(self, field):
        for a in (field.annotations or []):
            if a.name != "JoinTable":
                continue
            name = self._ann_kv(a, "name")
            join_col = self._ann_nested_joincol(a, "joinColumns")
            inv_col = self._ann_nested_joincol(a, "inverseJoinColumns")
            if name and join_col and inv_col:
                return name, join_col, inv_col
        return None

    def _ann_kv(self, ann, key: str):
        pairs = ann.element if isinstance(ann.element, list) else ([ann.element] if ann.element else [])
        for p in pairs:
            if getattr(p, "name", None) == key:
                return self._literal(getattr(p, "value", None))
        return None

    def _ann_nested_joincol(self, ann, key: str) -> str | None:
        pairs = ann.element if isinstance(ann.element, list) else ([ann.element] if ann.element else [])
        for p in pairs:
            if getattr(p, "name", None) != key:
                continue
            v = getattr(p, "value", None)
            if getattr(v, "name", None) == "JoinColumn":
                return self._ann_kv(v, "name")
        return None

    def _literal(self, node) -> str | None:
        if node is None:
            return None
        s = getattr(node, "value", None)
        if s is None:
            return None
        return s.strip("\"'")