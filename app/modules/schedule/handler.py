from fastapi import APIRouter
from app.inputs import Source
from app.pipeline import stages

router = APIRouter()

@router.post('/api/schedule')
def plan(source: Source):
    result = stages(source.raw(), source.pot_limit)
    return {'rows': result['accepted'], 'summary': result['schedule']}
