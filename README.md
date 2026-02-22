# ERD Agent (JPA → DBML)

Java JPA 기반 프로젝트의 소스 코드를 분석하여  
**dbdiagram.io에서 바로 시각화 가능한 DBML ERD 문서**를 자동 생성하는 도구입니다.

> 본 도구는 JPA(Java) 기반 Entity를 정적 분석하여
> 테이블, 컬럼, 관계(FK)를 추출하고 dbdiagram.io 호환 DBML로 변환합니다.  
> 복합 키, 상속 전략 등 고급 매핑은 향후 확장 또는 Azure OpenAI 보정 단계에서 지원 예정입니다.

---

## ✨ 주요 기능

- ✅ Java JPA Entity 자동 스캔 (`@Entity`, `@Table`)
- ✅ 컬럼 추출 (`@Id`, `@GeneratedValue`, `@Column`)
- ✅ 관계 추출 (`@ManyToOne`, `@OneToOne`, `@ManyToMany`)
- ✅ DBML 포맷으로 ERD 생성 (dbdiagram.io 호환)
- ✅ ERD 요약 Markdown 문서 자동 생성
- ✅ 파일 변경 감지 기반 ERD 자동 업데이트
- ✅ (옵션) Azure OpenAI로 스키마 보정

---

## 📁 프로젝트 구조
erd-agent/
├─ src/erd_agent/
│  ├─ agent.py          # CLI 진입점
│  ├─ scanner.py        # JPA Entity 파일 탐색
│  ├─ parsers/          # ORM 파서 (확장 가능)
│  │  ├─ init.py
│  │  └─ jpa_java.py
│  ├─ model.py          # Schea/Table/Column/Ref 모델
│  ├─ normalize.py     # 스키마 정합성 보정
│  ├─ dbml_writer.py   # DBML 생성
│  ├─ docs_writer.py   # ERD 요약 MD 생성
│  ├─ watch.py         # 자동 업데이트
│  └─ llm/             # Azure OpenAI 옵션
│
├─ notebooks/
│  └─ ERD_Agent.ipynb  # Jupyter 실행용
│
├─ docs/               # 설계 문서
├─ out/                # 생성 결과물
└─ README.md

---

## ⚙️ 설치

```bash
git clone <this-repo>
cd erd-agent
pip install -e .

---

Python 버전: 3.12 이상

---
🚀 사용 방법
1) 로컬 프로젝트 ERD 생성
```shell
erd-agent generate /path/to/java-project
```

결과:
```
out/
├─ database.dbml
└─ erd_summary.md
```

2) GitHub 레포에서 직접 생성
```shell
erd-agent generate https://github.com/org/repo.git
```
private repo는 .env에 GITHUB_TOKEN 설정

3) 자동 업데이트
```shell
erd-agent watch /path/to/java-project
```
.java 파일 변경 시 ERD 자동 재생성

---

🧩 지원하는 JPA 매핑
## ✅ Supported JPA Mappings

| JPA Annotation | 적용 위치 | ERD / DBML 변환 방식 | 비고 |
|---------------|----------|----------------------|------|
| `@Entity` | Class | Table 생성 | 엔티티 클래스 기준 테이블 생성 |
| `@Entity(name)` | Class | Table 이름 결정 | `name` 속성 우선 적용 |
| `@Table(name)` | Class | Table 이름 매핑 | 미지정 시 Entity 이름 사용 |
| `@Table(schema)` | Class | `schema.table` 형태로 생성 | DBML 스키마 지원 |
| `@Id` | Field | Primary Key (`pk`) | PK 컬럼으로 변환 |
| `@GeneratedValue` | Field | Auto Increment (`increment`) | `IDENTITY`, `AUTO` 등 공통 처리 |
| `@Column(name)` | Field | Column 이름 매핑 | 필드명 대신 name 사용 |
| `@Column(nullable)` | Field | `not null` 여부 | `nullable=false` → `not null` |
| `@Column(unique)` | Field | `unique` 제약 | DBML `unique` |
| `@Column(length)` | Field | `varchar(length)` | 문자열 타입에만 적용 |
| `@Enumerated` | Field | `varchar` 컬럼 | Enum 값 문자열 저장 기준 |
| `@ManyToOne` | Field | FK 컬럼 + `Ref` 생성 | 기본 FK: `<field>_id` |
| `@OneToOne` | Field | FK 컬럼 + `Ref` 생성 | 단방향 기준 |
| `@JoinColumn(name)` | Field | FK 컬럼명 지정 | 미지정 시 `<field>_id` |
| `@ManyToMany` | Field | Join Table 생성 | 단순 조인 테이블 |
| `@JoinTable` | Field | Join Table + FK 2개 | `joinColumns`, `inverseJoinColumns` 반영 |
| `@OneToMany(mappedBy)` | Field | (현재 스킵) | 양방향 분석은 향후 확장 |
| `@EmbeddedId` | Field | (미지원) | 향후 Azure OpenAI 보정 대상 |
| `@IdClass` | Class | (미지원) | 복합키 향후 지원 예정 |
| `@Inheritance` | Class | (미지원) | ERD 전략 정의 필요 |

---
🧠 Azure OpenAI (선택)
애매한 관계, 누락된 테이블, 복합 키 등
정적 분석만으로 어려운 경우 Azure OpenAI로 보정 가능

```shell
erd-agent generate /path/to/repo --use-aoai
```

---

🔧 확장성

✅ SQLAlchemy / Django ORM
✅ EF Core (C#)
✅ MyBatis XML
✅ ERD 외 설계 문서 자동 생성

➡️ parsers/ 폴더에 파서 추가만 하면 확장 가능

---

📌 출력 결과 활용

database.dbml → dbdiagram.io에 붙여넣기
erd_summary.md → 설계 문서 / 리뷰 자료로 활용