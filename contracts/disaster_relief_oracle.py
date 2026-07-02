# v0.2.16
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *

import json
import typing
from dataclasses import dataclass


@allow_storage
@dataclass
class ReliefRecord:
    disaster_claim: str
    source_url: str
    status: str  # VERIFIED | REJECTED | UNVERIFIABLE
    confidence: bigint
    evidence_summary: str


class Contract(gl.Contract):
    records: TreeMap[str, ReliefRecord]
    next_id: bigint

    def __init__(self):
        self.next_id = bigint(0)

    @gl.public.view
    def get_record(self, record_id: str) -> str:
        if record_id not in self.records:
            raise gl.vm.UserError("Relief record not found")
        
        record = self.records[record_id]
        return json.dumps({
            "id": record_id,
            "disaster_claim": record.disaster_claim,
            "source_url": record.source_url,
            "status": record.status,
            "confidence": int(record.confidence),
            "evidence_summary": record.evidence_summary
        })

    @gl.public.view
    def get_total_records(self) -> int:
        return int(self.next_id)
