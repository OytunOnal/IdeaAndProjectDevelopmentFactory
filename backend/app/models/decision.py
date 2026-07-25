from pydantic import BaseModel


class DecisionOption(BaseModel):
    id: str
    label: str
    description: str
    pros: list[str] = []
    cons: list[str] = []


class DecisionPoint(BaseModel):
    id: str
    agent: str
    category: str  # strategic, technical, content, quality
    question: str
    context: str = ""
    options: list[DecisionOption] = []
    agent_recommendation: str | None = None
    agent_reasoning: str | None = None
    allow_delegate: bool = True
    allow_freeform: bool = True


class DecisionSubmit(BaseModel):
    decision_id: str
    action: str  # choose, delegate, custom, more_info
    chosen_option: str | None = None
    custom_input: str | None = None
