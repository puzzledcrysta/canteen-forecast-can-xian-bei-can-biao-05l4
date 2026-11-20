from hashlib import sha256
from app.settings import RULE_VERSION


def manifest(raw,book,cap=None):
    source_hash,book_hash = sha256(raw).hexdigest(),sha256(book).hexdigest()
    run_id = sha256(f'{RULE_VERSION}:{source_hash}:{book_hash}:{cap}'.encode()).hexdigest()
    return {'run_id':run_id,'source_sha256':source_hash,'book_sha256':book_hash,
            'version':RULE_VERSION,'parameters':{'mode':'独立复算','pot_limit':cap}}
