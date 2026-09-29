"""AfyaPlus triage API. /health reports the prompt SHA and every runtime version."""
from fastapi import FastAPI
from pydantic import BaseModel, Field

from app import runtime as rt

app = FastAPI(title='AfyaPlus Triage', version=rt.RELEASE_VERSION)


class TriageIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


@app.get('/health')
def health():
    return rt.health_payload()


@app.post('/triage')
def triage(body: TriageIn):
    # Wire the Week 6 OpenAI client here: model/temperature/max_tokens from
    # rt.CONFIG, and always send rt.SYSTEM_PROMPT as the system message.
    return {
        'advice': '(model call uses SYSTEM_PROMPT, stub for lab)',
        'prompt_version': rt.PROMPT_VERSION,
        'release': rt.RELEASE_VERSION,
        'disclaimer': 'Not a diagnosis. Seek professional care when unsure.',
    }


if __name__ == '__main__':
    # Print pin material for prompts/pin.json
    print('PROMPT_VERSION', rt.PROMPT_VERSION)
    print('PROMPT_SHA256', rt.PROMPT_SHA256)
