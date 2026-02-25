"""models.py のテスト"""

from company_data_generator.models import (
    AutoCompletedProfile,
    CompanyProfile,
    DocumentPlan,
    DocumentPlanList,
    GeneratedDocument,
    MissingInfo,
    PhaseTokenUsage,
    TokenUsage,
)


class TestCompanyProfile:
    def test_create(self, sample_profile: CompanyProfile) -> None:
        assert sample_profile.name == "株式会社テスト商事"
        assert sample_profile.employee_count == 100
        assert len(sample_profile.departments) == 4

    def test_json_roundtrip(self, sample_profile: CompanyProfile) -> None:
        json_str = sample_profile.model_dump_json(ensure_ascii=False)
        restored = CompanyProfile.model_validate_json(json_str)
        assert restored == sample_profile


class TestDocumentPlan:
    def test_create(self, sample_plan: DocumentPlan) -> None:
        assert sample_plan.title == "情報セキュリティポリシー"
        assert sample_plan.includes_diagram is True

    def test_plan_list(self, sample_plan_list: DocumentPlanList) -> None:
        assert sample_plan_list.domain == "営業"
        assert len(sample_plan_list.plans) == 1


class TestGeneratedDocument:
    def test_create(self, sample_generated_document: GeneratedDocument) -> None:
        assert sample_generated_document.filename.endswith(".md")
        assert "情報セキュリティポリシー" in sample_generated_document.content


class TestMissingInfo:
    def test_create(self) -> None:
        info = MissingInfo(questions=["従業員数は？", "主要な取引先は？"])
        assert len(info.questions) == 2


class TestAutoCompletedProfile:
    def test_create(self, sample_profile: CompanyProfile) -> None:
        auto = AutoCompletedProfile(
            profile=sample_profile,
            assumptions=["従業員数は100名と推定"],
        )
        assert auto.profile.name == "株式会社テスト商事"
        assert len(auto.assumptions) == 1


class TestTokenUsage:
    def test_defaults(self) -> None:
        usage = TokenUsage()
        assert usage.prompt_tokens == 0
        assert usage.completion_tokens == 0
        assert usage.total_tokens == 0

    def test_total(self) -> None:
        usage = TokenUsage(prompt_tokens=100, completion_tokens=50)
        assert usage.total_tokens == 150

    def test_iadd(self) -> None:
        a = TokenUsage(prompt_tokens=10, completion_tokens=20)
        b = TokenUsage(prompt_tokens=30, completion_tokens=40)
        a += b
        assert a.prompt_tokens == 40
        assert a.completion_tokens == 60
        assert a.total_tokens == 100


class TestPhaseTokenUsage:
    def test_defaults(self) -> None:
        pu = PhaseTokenUsage()
        assert pu.phase1.total_tokens == 0
        assert pu.phase2.total_tokens == 0
        assert pu.phase3.total_tokens == 0
        assert pu.phase3_doc_count == 0

    def test_set_phases(self) -> None:
        pu = PhaseTokenUsage(
            phase1=TokenUsage(prompt_tokens=100, completion_tokens=50),
            phase2=TokenUsage(prompt_tokens=200, completion_tokens=100),
            phase3=TokenUsage(prompt_tokens=1000, completion_tokens=500),
            phase3_doc_count=5,
        )
        assert pu.phase1.total_tokens == 150
        assert pu.phase2.total_tokens == 300
        assert pu.phase3.total_tokens == 1500
