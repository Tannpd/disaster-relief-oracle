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


def _normalize_status(status: str) -> str:
    s = str(status or "").strip().upper()
    if "VERIFIED" in s or "VERIFY" in s:
        return "VERIFIED"
    if "REJECT" in s or "REJECTED" in s:
        return "REJECTED"
    if "UNVERIFIABLE" in s or "UNVERIFIED" in s:
        return "UNVERIFIABLE"
    return "UNVERIFIABLE"


def _normalize_confidence(conf_val: typing.Any) -> int:
    try:
        c = int(conf_val)
    except Exception:
        c = 0
    return max(0, min(100, c))


class Contract(gl.Contract):
    records: TreeMap[str, ReliefRecord]
    next_id: bigint

    def __init__(self):
        self.next_id = bigint(0)

    @gl.public.write
    def verify_disaster(self, disaster_claim: str, source_url: str) -> None:
        if not disaster_claim or not disaster_claim.strip():
            raise gl.vm.UserError("disaster_claim must not be empty")
        if not source_url or not source_url.strip():
            raise gl.vm.UserError("source_url must not be empty")

        url_clean = source_url.strip()
        url_lower = url_clean.lower()
        if not (url_lower.startswith("http://") or url_lower.startswith("https://")):
            raise gl.vm.UserError("source_url must start with http:// or https://")

        claim_clean = disaster_claim.strip()

        def leader_fn() -> str:
            # Fetch content from webpage
            web_content = gl.nondet.web.render(url_clean, mode="text")
            
            # Truncate content to fit in LLM context limits safely
            web_content_truncated = (web_content or "").strip()[:6000]

            prompt = f"""You are a strict disaster relief auditor.
Cross-reference the disaster claim details with the fetched page content to verify if the emergency event is actively confirmed.

DISASTER CLAIM TO AUDIT:
---
{claim_clean}
---

FETCHED REFERENCE PAGE CONTENT:
---
{web_content_truncated}
---

Rules for audit:
- Assign "VERIFIED" if the reference page content clearly confirms the disaster details (e.g. confirms a state of emergency, severe flooding, earthquake damage, or evacuation order matching the location and date in the claim).
- Assign "REJECTED" if the reference page content clearly contradicts the claim details (e.g. indicates the area is completely unaffected, or the event mentioned is completely different like an earthquake claim when the article only reports a minor rainfall).
- Assign "UNVERIFIABLE" if the reference page content lacks sufficient information, is unrelated (e.g. an advertisement or travel blog that doesn't mention emergency details), or has no relevant verification data.
- Assign a confidence score from 0 to 100 representing how confident you are in this qualitative assessment.
- Provide a brief evidence summary (maximum 200 characters) explaining the audit findings.

Respond ONLY with a valid JSON object matching the following structure:
{{
  "status": "VERIFIED" | "REJECTED" | "UNVERIFIABLE",
  "confidence": <integer 0-100>,
  "evidence_summary": "summary message string"
}}"""
            res = gl.nondet.exec_prompt(prompt, response_format="json")
            if not isinstance(res, dict):
                res = {}

            status = _normalize_status(res.get("status", "UNVERIFIABLE"))
            confidence = _normalize_confidence(res.get("confidence", 0))
            evidence_summary = str(res.get("evidence_summary", "")).strip()[:200]
            if not evidence_summary:
                evidence_summary = "No evidence summary provided."

            return json.dumps({
                "status": status,
                "confidence": confidence,
                "evidence_summary": evidence_summary
            }, sort_keys=True)

        def validator_fn(leader_res: typing.Any) -> bool:
            if not isinstance(leader_res, gl.vm.Return):
                return False
            try:
                leader_data = json.loads(leader_res.calldata)
            except Exception:
                return False

            leader_status = _normalize_status(leader_data.get("status"))
            leader_confidence = _normalize_confidence(leader_data.get("confidence"))

            try:
                mine_json = leader_fn()
                mine_data = json.loads(mine_json)
            except Exception:
                return False

            mine_status = _normalize_status(mine_data.get("status"))
            mine_confidence = _normalize_confidence(mine_data.get("confidence"))

            if leader_status != mine_status:
                return False

            if abs(leader_confidence - mine_confidence) > 15:
                return False

            return True

        raw_result = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
        payload = json.loads(raw_result)

        rid = str(self.next_id)
        self.records[rid] = ReliefRecord(
            disaster_claim=claim_clean,
            source_url=url_clean,
            status=_normalize_status(payload.get("status")),
            confidence=bigint(_normalize_confidence(payload.get("confidence"))),
            evidence_summary=str(payload.get("evidence_summary")).strip()[:200]
        )
        self.next_id = self.next_id + bigint(1)

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
