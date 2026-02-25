"""Pydantic データモデル定義"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CompanyProfile(BaseModel):
    """会社情報の完全なプロファイル"""

    name: str = Field(description="会社名")
    industry: str = Field(description="業種")
    employee_count: int = Field(description="従業員数")
    founded_year: int = Field(description="設立年")
    headquarters: str = Field(description="本社所在地")
    business_description: str = Field(description="事業概要")
    departments: list[str] = Field(description="部署一覧")
    additional_context: dict[str, str] = Field(
        default_factory=dict, description="ドメイン別追加情報"
    )


class DocumentPlan(BaseModel):
    """生成するドキュメント1件の計画"""

    title: str = Field(description="ドキュメントタイトル")
    doc_type: str = Field(description="種別 (内規, 議事録, 報告書, マニュアル, etc.)")
    summary: str = Field(description="概要 (200字程度)")
    target_audience: str = Field(description="対象読者")
    includes_diagram: bool = Field(description="Mermaid図を含むか")
    estimated_length: str = Field(description="想定ボリューム (short / medium / long)")


class DocumentPlanList(BaseModel):
    """ドキュメント計画リスト"""

    domain: str = Field(description="対象ドメイン")
    plans: list[DocumentPlan] = Field(description="計画リスト")


class GeneratedDocument(BaseModel):
    """生成されたドキュメント"""

    plan: DocumentPlan = Field(description="元の計画")
    content: str = Field(description="生成されたMarkdown本文")
    filename: str = Field(description="出力ファイル名")


class MissingInfo(BaseModel):
    """不足情報の分析結果"""

    questions: list[str] = Field(description="ユーザに尋ねるべき質問のリスト")


class AutoCompletedProfile(BaseModel):
    """LLMが自動補完した会社プロファイル"""

    profile: CompanyProfile = Field(description="補完された会社プロファイル")
    assumptions: list[str] = Field(description="補完時に設定した前提条件のリスト")
