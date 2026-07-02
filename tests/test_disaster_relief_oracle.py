import pytest
import json

def test_initial_state(direct_deploy):
    # Deploy contract and check initial count is 0
    contract = direct_deploy("contracts/disaster_relief_oracle.py", sdk_version="v0.2.16")
    assert contract.get_total_records() == 0

def test_input_validation(direct_deploy, direct_vm):
    contract = direct_deploy("contracts/disaster_relief_oracle.py", sdk_version="v0.2.16")
    
    # Test empty disaster_claim
    with pytest.raises(Exception) as excinfo:
        contract.verify_disaster("", "https://example.com/news")
    assert "disaster_claim must not be empty" in str(excinfo.value)
    
    # Test empty source_url
    with pytest.raises(Exception) as excinfo:
        contract.verify_disaster("Severe flooding", "")
    assert "source_url must not be empty" in str(excinfo.value)

    # Test invalid URL protocol
    with pytest.raises(Exception) as excinfo:
        contract.verify_disaster("Severe flooding", "ftp://example.com/news")
    assert "source_url must start with http:// or https://" in str(excinfo.value)

def test_verify_disaster_happy_path(direct_deploy, direct_vm):
    contract = direct_deploy("contracts/disaster_relief_oracle.py", sdk_version="v0.2.16")
    
    # Mock web page rendering
    direct_vm.mock_web(
        r".*example\.com.*",
        {"method": "GET", "status": 200, "body": "Emergency Alert: Typhoon Yagi caused severe flooding in the northern region. A state of emergency has been declared."}
    )

    # Mock LLM status
    direct_vm.mock_llm(
        r".*",
        '{"status": "VERIFIED", "confidence": 98, "evidence_summary": "The emergency alert confirms that severe flooding and a state of emergency were declared in the northern region."}'
    )
    
    # Execute evaluation
    contract.verify_disaster(
        disaster_claim="Region A is under a state of emergency due to severe flooding.",
        source_url="https://example.com/news-alert"
    )
    
    assert contract.get_total_records() == 1
    
    # Retrieve and parse record
    record_json = contract.get_record("0")
    record = json.loads(record_json)
    
    assert record["id"] == "0"
    assert record["disaster_claim"] == "Region A is under a state of emergency due to severe flooding."
    assert record["source_url"] == "https://example.com/news-alert"
    assert record["status"] == "VERIFIED"
    assert record["confidence"] == 98
    assert record["evidence_summary"] == "The emergency alert confirms that severe flooding and a state of emergency were declared in the northern region."
