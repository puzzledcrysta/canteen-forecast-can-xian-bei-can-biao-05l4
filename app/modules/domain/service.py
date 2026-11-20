from app.errors import DataError
from app.evidence import finding
from app.settings import UNIT
from .rule import evaluate
from .values import whole


def calculate(records):
    accepted, rejected = [],[]
    for record in records:
        try:
            amount, proof = evaluate(record['fields'])
            pot = whole(record['fields']['每锅份数'],1,1000)
        except DataError as error:
            rejected.append(finding(record,error.code,str(error)))
            continue
        accepted.append({'key':record['key'],'line':record['line'],'revision':record['revision'],
                         'amount':format(amount,'f'),'unit':UNIT,'raw':record['raw'],
                         'pots':int(amount)//pot,'pot_size':pot,
                         'proof':[{'metric':label,'value':str(value),'unit':unit} for label,value,unit in proof]})
    return accepted,rejected
