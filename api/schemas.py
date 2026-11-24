from pydantic import BaseModel, Field, field_validator

MAX_CHARS = 20_000


class ExtractRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_CHARS, description="Texte anglais à analyser")

    @field_validator("text")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("le texte est vide")
        return v


class Entity(BaseModel):
    text: str
    label: str
    start: int = Field(description="Position du premier caractère dans le texte envoyé")
    end: int = Field(description="Position après le dernier caractère")


class ExtractResponse(BaseModel):
    entities: list[Entity]
    weapons: list[str]
    mil_units: list[str]
    mil_orgs: list[str]
    model: str
    latency_ms: float


class HealthResponse(BaseModel):
    status: str
    model: str
    labels: list[str]
