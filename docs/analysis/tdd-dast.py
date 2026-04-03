"""
TDD Test Cases — DAST Integration
Derived from: docs/analysis/dast-integration-analysis.md

Run with: pytest docs/analysis/tdd-dast.py -v
These are specification tests — they define the expected contract BEFORE implementation.
All tests will fail until the corresponding code is written.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures — raw tool output samples
# ---------------------------------------------------------------------------


@pytest.fixture
def zap_output_single():
    return json.dumps(
        {
            "alerts": [
                {
                    "alert": "SQL Injection",
                    "riskcode": "3",  # 3 = High
                    "confidence": "2",
                    "uri": "https://app.example.com/api/users?id=1",
                    "param": "id",
                    "description": "SQL injection vulnerability detected.",
                    "cweid": "89",
                    "wascid": "19",
                }
            ]
        }
    )


@pytest.fixture
def zap_output_multi():
    return json.dumps(
        {
            "alerts": [
                {
                    "alert": "SQL Injection",
                    "riskcode": "3",
                    "confidence": "2",
                    "uri": "https://app.example.com/login",
                    "param": "username",
                    "description": "SQLi",
                    "cweid": "89",
                    "wascid": "19",
                },
                {
                    "alert": "XSS",
                    "riskcode": "2",
                    "confidence": "2",
                    "uri": "https://app.example.com/search",
                    "param": "q",
                    "description": "XSS",
                    "cweid": "79",
                    "wascid": "8",
                },
                {
                    "alert": "Info Disclosure",
                    "riskcode": "1",
                    "confidence": "1",
                    "uri": "https://app.example.com/debug",
                    "param": "",
                    "description": "Info",
                    "cweid": "200",
                    "wascid": "13",
                },
                {
                    "alert": "Cookie No HttpOnly",
                    "riskcode": "0",
                    "confidence": "2",
                    "uri": "https://app.example.com",
                    "param": "session",
                    "description": "Cookie",
                    "cweid": "614",
                    "wascid": "13",
                },
            ]
        }
    )


@pytest.fixture
def zap_output_empty():
    return json.dumps({"alerts": []})


@pytest.fixture
def nuclei_output_single():
    # Nuclei emits JSONL — one JSON object per finding
    return json.dumps(
        {
            "template-id": "cves/2023/CVE-2023-1234",
            "info": {
                "name": "Remote Code Execution",
                "severity": "critical",
                "tags": ["cve", "rce"],
            },
            "matched-at": "https://app.example.com/admin/exec",
            "type": "http",
            "timestamp": "2026-04-03T10:00:00Z",
        }
    )


@pytest.fixture
def burp_output_single():
    return json.dumps(
        {
            "issues": [
                {
                    "issue_type": "SQL injection",
                    "severity": "High",
                    "path": "/api/v1/users",
                    "description": "Potential SQL injection in parameter 'id'.",
                }
            ]
        }
    )


@pytest.fixture
def nikto_output_single():
    return json.dumps(
        {
            "vulnerabilities": [
                {
                    "msg": "Server leaks inodes via ETags.",
                    "uri": "/",
                    "OSVDB": "3092",
                }
            ]
        }
    )


@pytest.fixture
def mock_product_id():
    return "prod-dast-001"


@pytest.fixture
def mock_pipeline_run_id():
    return "run-dast-001"


@pytest.fixture
def mock_task_run_id():
    return "taskrun-dast-001"


# ---------------------------------------------------------------------------
# Group 1: ingest_findings — ZAP
# ---------------------------------------------------------------------------


class TestIngestFindingsZap:
    def test_single_alert_creates_one_finding(
        self, zap_output_single, mock_task_run_id, mock_pipeline_run_id
    ):
        from app.services.dast_service import ingest_findings

        with patch("app.services.dast_service.db"):
            findings = ingest_findings(
                mock_task_run_id, mock_pipeline_run_id, "zap", zap_output_single
            )
            assert len(findings) == 1

    def test_riskcode_3_maps_to_high(
        self, zap_output_single, mock_task_run_id, mock_pipeline_run_id
    ):
        from app.services.dast_service import ingest_findings

        with patch("app.services.dast_service.db"):
            findings = ingest_findings(
                mock_task_run_id, mock_pipeline_run_id, "zap", zap_output_single
            )
            assert findings[0].severity == "high"

    def test_riskcode_2_maps_to_medium(self, mock_task_run_id, mock_pipeline_run_id):
        from app.services.dast_service import ingest_findings

        raw = json.dumps(
            {
                "alerts": [
                    {
                        "alert": "XSS",
                        "riskcode": "2",
                        "confidence": "2",
                        "uri": "http://x.com",
                        "param": "q",
                        "description": "XSS",
                        "cweid": "79",
                        "wascid": "8",
                    }
                ]
            }
        )
        with patch("app.services.dast_service.db"):
            findings = ingest_findings(mock_task_run_id, mock_pipeline_run_id, "zap", raw)
            assert findings[0].severity == "medium"

    def test_riskcode_1_maps_to_low(self, mock_task_run_id, mock_pipeline_run_id):
        from app.services.dast_service import ingest_findings

        raw = json.dumps(
            {
                "alerts": [
                    {
                        "alert": "Info",
                        "riskcode": "1",
                        "confidence": "1",
                        "uri": "http://x.com",
                        "param": "",
                        "description": "I",
                        "cweid": "200",
                        "wascid": "13",
                    }
                ]
            }
        )
        with patch("app.services.dast_service.db"):
            findings = ingest_findings(mock_task_run_id, mock_pipeline_run_id, "zap", raw)
            assert findings[0].severity == "low"

    def test_riskcode_0_maps_to_info(self, mock_task_run_id, mock_pipeline_run_id):
        from app.services.dast_service import ingest_findings

        raw = json.dumps(
            {
                "alerts": [
                    {
                        "alert": "Cookie",
                        "riskcode": "0",
                        "confidence": "2",
                        "uri": "http://x.com",
                        "param": "sess",
                        "description": "C",
                        "cweid": "614",
                        "wascid": "13",
                    }
                ]
            }
        )
        with patch("app.services.dast_service.db"):
            findings = ingest_findings(mock_task_run_id, mock_pipeline_run_id, "zap", raw)
            assert findings[0].severity == "info"

    def test_multi_alert_creates_all_findings(
        self, zap_output_multi, mock_task_run_id, mock_pipeline_run_id
    ):
        from app.services.dast_service import ingest_findings

        with patch("app.services.dast_service.db"):
            findings = ingest_findings(
                mock_task_run_id, mock_pipeline_run_id, "zap", zap_output_multi
            )
            assert len(findings) == 4

    def test_empty_alerts_returns_empty(
        self, zap_output_empty, mock_task_run_id, mock_pipeline_run_id
    ):
        from app.services.dast_service import ingest_findings

        with patch("app.services.dast_service.db"):
            findings = ingest_findings(
                mock_task_run_id, mock_pipeline_run_id, "zap", zap_output_empty
            )
            assert findings == []

    def test_finding_has_url_and_cwe(
        self, zap_output_single, mock_task_run_id, mock_pipeline_run_id
    ):
        from app.services.dast_service import ingest_findings

        with patch("app.services.dast_service.db"):
            f = ingest_findings(mock_task_run_id, mock_pipeline_run_id, "zap", zap_output_single)[0]
            assert "example.com" in f.url
            assert f.cwe_id == "89"

    def test_tool_field_set_to_zap(self, zap_output_single, mock_task_run_id, mock_pipeline_run_id):
        from app.services.dast_service import ingest_findings

        with patch("app.services.dast_service.db"):
            f = ingest_findings(mock_task_run_id, mock_pipeline_run_id, "zap", zap_output_single)[0]
            assert f.tool == "zap"

    def test_finding_status_defaults_to_open(
        self, zap_output_single, mock_task_run_id, mock_pipeline_run_id
    ):
        from app.services.dast_service import ingest_findings

        with patch("app.services.dast_service.db"):
            f = ingest_findings(mock_task_run_id, mock_pipeline_run_id, "zap", zap_output_single)[0]
            assert f.status == "open"

    def test_malformed_json_raises(self, mock_task_run_id, mock_pipeline_run_id):
        from app.services.dast_service import ingest_findings

        with pytest.raises((ValueError, json.JSONDecodeError)):
            ingest_findings(mock_task_run_id, mock_pipeline_run_id, "zap", "NOT JSON")


# ---------------------------------------------------------------------------
# Group 2: ingest_findings — Nuclei
# ---------------------------------------------------------------------------


class TestIngestFindingsNuclei:
    def test_nuclei_critical_parsed(
        self, nuclei_output_single, mock_task_run_id, mock_pipeline_run_id
    ):
        from app.services.dast_service import ingest_findings

        with patch("app.services.dast_service.db"):
            findings = ingest_findings(
                mock_task_run_id, mock_pipeline_run_id, "nuclei", nuclei_output_single
            )
            assert len(findings) == 1
            assert findings[0].severity == "critical"

    def test_nuclei_url_from_matched_at(
        self, nuclei_output_single, mock_task_run_id, mock_pipeline_run_id
    ):
        from app.services.dast_service import ingest_findings

        with patch("app.services.dast_service.db"):
            f = ingest_findings(
                mock_task_run_id, mock_pipeline_run_id, "nuclei", nuclei_output_single
            )[0]
            assert "admin/exec" in f.url

    def test_nuclei_title_from_info_name(
        self, nuclei_output_single, mock_task_run_id, mock_pipeline_run_id
    ):
        from app.services.dast_service import ingest_findings

        with patch("app.services.dast_service.db"):
            f = ingest_findings(
                mock_task_run_id, mock_pipeline_run_id, "nuclei", nuclei_output_single
            )[0]
            assert "Remote Code Execution" in f.title

    def test_nuclei_tool_field_set(
        self, nuclei_output_single, mock_task_run_id, mock_pipeline_run_id
    ):
        from app.services.dast_service import ingest_findings

        with patch("app.services.dast_service.db"):
            f = ingest_findings(
                mock_task_run_id, mock_pipeline_run_id, "nuclei", nuclei_output_single
            )[0]
            assert f.tool == "nuclei"


# ---------------------------------------------------------------------------
# Group 3: ingest_findings — Burp
# ---------------------------------------------------------------------------


class TestIngestFindingsBurp:
    def test_burp_high_mapped_correctly(
        self, burp_output_single, mock_task_run_id, mock_pipeline_run_id
    ):
        from app.services.dast_service import ingest_findings

        with patch("app.services.dast_service.db"):
            findings = ingest_findings(
                mock_task_run_id, mock_pipeline_run_id, "burp", burp_output_single
            )
            assert findings[0].severity == "high"

    def test_burp_path_used_as_url(
        self, burp_output_single, mock_task_run_id, mock_pipeline_run_id
    ):
        from app.services.dast_service import ingest_findings

        with patch("app.services.dast_service.db"):
            f = ingest_findings(mock_task_run_id, mock_pipeline_run_id, "burp", burp_output_single)[
                0
            ]
            assert "/api/v1/users" in f.url

    def test_burp_tool_field_set(self, burp_output_single, mock_task_run_id, mock_pipeline_run_id):
        from app.services.dast_service import ingest_findings

        with patch("app.services.dast_service.db"):
            f = ingest_findings(mock_task_run_id, mock_pipeline_run_id, "burp", burp_output_single)[
                0
            ]
            assert f.tool == "burp"


# ---------------------------------------------------------------------------
# Group 4: ingest_findings — Nikto
# ---------------------------------------------------------------------------


class TestIngestFindingsNikto:
    def test_nikto_finding_created(
        self, nikto_output_single, mock_task_run_id, mock_pipeline_run_id
    ):
        from app.services.dast_service import ingest_findings

        with patch("app.services.dast_service.db"):
            findings = ingest_findings(
                mock_task_run_id, mock_pipeline_run_id, "nikto", nikto_output_single
            )
            assert len(findings) == 1

    def test_nikto_osvdb_presence_maps_to_medium(
        self, nikto_output_single, mock_task_run_id, mock_pipeline_run_id
    ):
        from app.services.dast_service import ingest_findings

        with patch("app.services.dast_service.db"):
            f = ingest_findings(
                mock_task_run_id, mock_pipeline_run_id, "nikto", nikto_output_single
            )[0]
            assert f.severity == "medium"


# ---------------------------------------------------------------------------
# Group 5: calculate_dast_impact
# ---------------------------------------------------------------------------


class TestCalculateDastImpact:
    def test_no_findings_zero_delta(self, mock_pipeline_run_id):
        from app.services.dast_service import calculate_dast_impact

        with patch("app.services.dast_service.SecurityFinding") as mock_model:
            mock_model.query.filter_by.return_value.all.return_value = []
            mandatory_delta, runtime_delta = calculate_dast_impact(mock_pipeline_run_id)
            assert mandatory_delta == 0.0
            assert runtime_delta == 0.0

    def test_three_critical_deducts_15_mandatory(self, mock_pipeline_run_id):
        from app.services.dast_service import calculate_dast_impact

        with patch("app.services.dast_service.SecurityFinding") as mock_model:
            findings = [MagicMock(severity="critical", status="open") for _ in range(3)]
            mock_model.query.filter_by.return_value.all.return_value = findings
            mandatory_delta, _ = calculate_dast_impact(mock_pipeline_run_id)
            assert mandatory_delta == pytest.approx(-15.0)

    def test_critical_deduction_capped_at_minus_30(self, mock_pipeline_run_id):
        from app.services.dast_service import calculate_dast_impact

        with patch("app.services.dast_service.SecurityFinding") as mock_model:
            findings = [MagicMock(severity="critical", status="open") for _ in range(10)]
            mock_model.query.filter_by.return_value.all.return_value = findings
            mandatory_delta, _ = calculate_dast_impact(mock_pipeline_run_id)
            assert mandatory_delta >= -30.0

    def test_high_findings_deduct_runtime(self, mock_pipeline_run_id):
        from app.services.dast_service import calculate_dast_impact

        with patch("app.services.dast_service.SecurityFinding") as mock_model:
            findings = [MagicMock(severity="high", status="open") for _ in range(3)]
            mock_model.query.filter_by.return_value.all.return_value = findings
            _, runtime_delta = calculate_dast_impact(mock_pipeline_run_id)
            assert runtime_delta == pytest.approx(-6.0)

    def test_high_deduction_capped_at_minus_10(self, mock_pipeline_run_id):
        from app.services.dast_service import calculate_dast_impact

        with patch("app.services.dast_service.SecurityFinding") as mock_model:
            findings = [MagicMock(severity="high", status="open") for _ in range(10)]
            mock_model.query.filter_by.return_value.all.return_value = findings
            _, runtime_delta = calculate_dast_impact(mock_pipeline_run_id)
            assert runtime_delta >= -10.0

    def test_remediated_findings_not_counted(self, mock_pipeline_run_id):
        from app.services.dast_service import calculate_dast_impact

        with patch("app.services.dast_service.SecurityFinding") as mock_model:
            # Return only remediated findings
            mock_model.query.filter_by.return_value.filter.return_value.all.return_value = []
            mandatory_delta, runtime_delta = calculate_dast_impact(mock_pipeline_run_id)
            assert mandatory_delta == 0.0
            assert runtime_delta == 0.0


# ---------------------------------------------------------------------------
# Group 6: triage_finding
# ---------------------------------------------------------------------------


class TestTriageFinding:
    def test_valid_triage_status_accepted(self):
        from app.services.dast_service import triage_finding

        mock_finding = MagicMock(status="open")
        with patch("app.services.dast_service.SecurityFinding") as mock_model:
            mock_model.query.get.return_value = mock_finding
            with patch("app.services.dast_service.db"):
                result = triage_finding("finding-1", "triaged", None, "user-1")
                assert result.status == "triaged"

    def test_false_positive_requires_reason(self):
        from app.services.dast_service import triage_finding

        mock_finding = MagicMock(status="open")
        with patch("app.services.dast_service.SecurityFinding") as mock_model:
            mock_model.query.get.return_value = mock_finding
            with pytest.raises(ValueError, match="reason"):
                triage_finding("finding-1", "false_positive", None, "user-1")

    def test_invalid_status_raises(self):
        from app.services.dast_service import triage_finding

        with pytest.raises(ValueError):
            triage_finding("finding-1", "deleted", None, "user-1")

    def test_nonexistent_finding_raises(self):
        from app.services.dast_service import triage_finding

        with patch("app.services.dast_service.SecurityFinding") as mock_model:
            mock_model.query.get.return_value = None
            with pytest.raises((ValueError, LookupError)):
                triage_finding("nonexistent", "triaged", None, "user-1")

    def test_triage_sets_triaged_by_and_at(self):
        from app.services.dast_service import triage_finding

        mock_finding = MagicMock(status="open", triaged_by=None, triaged_at=None)
        with patch("app.services.dast_service.SecurityFinding") as mock_model:
            mock_model.query.get.return_value = mock_finding
            with patch("app.services.dast_service.db"):
                triage_finding("finding-1", "triaged", None, "user-42")
                assert mock_finding.triaged_by == "user-42"
                assert mock_finding.triaged_at is not None

    def test_triage_emits_audit_event(self):
        from app.services.dast_service import triage_finding

        mock_finding = MagicMock(status="open")
        with patch("app.services.dast_service.SecurityFinding") as mock_model:
            mock_model.query.get.return_value = mock_finding
            with patch("app.services.dast_service.db"):
                with patch("app.services.dast_service.AuditEvent") as mock_audit:
                    triage_finding("finding-1", "triaged", None, "user-1")
                    mock_audit.assert_called_once()


# ---------------------------------------------------------------------------
# Group 7: create_scan_profile
# ---------------------------------------------------------------------------


class TestCreateScanProfile:
    def test_valid_profile_persisted(self, mock_product_id):
        from app.services.dast_service import create_scan_profile

        data = {
            "name": "Prod ZAP Scan",
            "target_url": "https://app.example.com",
            "auth_type": "bearer",
            "auth_config": {"vault_ref": "prod/api-token"},
            "skip_patterns": [],
            "tool": "zap",
            "tool_config": {},
            "max_severity_to_pass": "high",
        }
        with patch("app.services.dast_service.db"):
            with patch("app.services.dast_service.DastScanProfile") as mock_model:
                mock_instance = MagicMock()
                mock_model.return_value = mock_instance
                result = create_scan_profile(mock_product_id, data, "user-1")
                assert result is not None

    def test_missing_target_url_raises(self, mock_product_id):
        from app.services.dast_service import create_scan_profile

        data = {"name": "No URL", "tool": "zap", "auth_type": "none"}
        with pytest.raises((ValueError, KeyError)):
            create_scan_profile(mock_product_id, data, "user-1")

    def test_invalid_tool_raises(self, mock_product_id):
        from app.services.dast_service import create_scan_profile

        data = {
            "name": "Bad Tool",
            "target_url": "http://x.com",
            "tool": "nmap",
            "auth_type": "none",
        }
        with pytest.raises(ValueError):
            create_scan_profile(mock_product_id, data, "user-1")

    def test_auth_config_never_stores_raw_credentials(self, mock_product_id):
        """auth_config must only accept vault references, not raw tokens."""
        from app.services.dast_service import create_scan_profile

        data = {
            "name": "Test",
            "target_url": "http://x.com",
            "tool": "zap",
            "auth_type": "bearer",
            "auth_config": {"token": "eyJhbGciOi..."},  # raw token — must be rejected
        }
        with pytest.raises(ValueError, match="vault"):
            create_scan_profile(mock_product_id, data, "user-1")


# ---------------------------------------------------------------------------
# Group 8: API Routes
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    from app import create_app

    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.test_client() as c:
        with app.app_context():
            from app.extensions import db

            db.create_all()
        yield c


@pytest.fixture
def auth_headers(client):
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
    token = resp.get_json().get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


class TestDastRoutes:
    def test_create_profile_returns_201(self, client, auth_headers, mock_product_id):
        payload = {
            "name": "Test Profile",
            "target_url": "https://app.example.com",
            "tool": "zap",
            "auth_type": "none",
            "max_severity_to_pass": "high",
        }
        with patch("app.routes.dast.dast_service.create_scan_profile") as mock_svc:
            mock_svc.return_value = MagicMock(id="prof-1")
            resp = client.post(
                f"/api/v1/products/{mock_product_id}/dast-profiles",
                json=payload,
                headers=auth_headers,
            )
            assert resp.status_code == 201

    def test_list_profiles_returns_200(self, client, auth_headers, mock_product_id):
        with patch("app.routes.dast.dast_service") as mock_svc:
            mock_svc.list_profiles.return_value = []
            resp = client.get(
                f"/api/v1/products/{mock_product_id}/dast-profiles",
                headers=auth_headers,
            )
            assert resp.status_code == 200

    def test_run_scan_returns_202(self, client, auth_headers):
        with patch("app.routes.dast.dast_service") as mock_svc:
            mock_svc.trigger_scan.return_value = MagicMock(id="taskrun-1")
            resp = client.post("/api/v1/dast-profiles/prof-1/run", headers=auth_headers)
            assert resp.status_code in (200, 202)

    def test_get_findings_for_run(self, client, auth_headers, mock_pipeline_run_id):
        with patch("app.routes.dast.dast_service.get_findings") as mock_get:
            mock_get.return_value = {"findings": [], "total": 0}
            resp = client.get(
                f"/api/v1/pipeline-runs/{mock_pipeline_run_id}/findings",
                headers=auth_headers,
            )
            assert resp.status_code == 200

    def test_get_findings_severity_filter(self, client, auth_headers, mock_pipeline_run_id):
        with patch("app.routes.dast.dast_service.get_findings") as mock_get:
            mock_get.return_value = {"findings": [], "total": 0}
            resp = client.get(
                f"/api/v1/pipeline-runs/{mock_pipeline_run_id}/findings?severity=critical",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            mock_get.assert_called_once()
            call_kwargs = mock_get.call_args
            assert "critical" in str(call_kwargs)

    def test_patch_finding_triage(self, client, auth_headers):
        with patch("app.routes.dast.dast_service.triage_finding") as mock_triage:
            mock_triage.return_value = MagicMock(status="triaged")
            resp = client.patch(
                "/api/v1/findings/finding-1",
                json={"status": "triaged"},
                headers=auth_headers,
            )
            assert resp.status_code in (200, 204)

    def test_product_summary_endpoint(self, client, auth_headers, mock_product_id):
        with patch("app.routes.dast.dast_service") as mock_svc:
            mock_svc.get_product_finding_summary.return_value = {
                "critical": 1,
                "high": 3,
                "medium": 5,
                "low": 10,
                "total": 19,
            }
            resp = client.get(
                f"/api/v1/products/{mock_product_id}/findings/summary",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert "total" in data

    def test_create_profile_requires_dast_configure_permission(self, client, mock_product_id):
        """Without dast:configure permission, profile creation must be rejected."""
        # No auth headers → unauthenticated
        resp = client.post(
            f"/api/v1/products/{mock_product_id}/dast-profiles",
            json={"name": "x", "target_url": "http://y.com", "tool": "zap"},
        )
        assert resp.status_code in (401, 403)

    def test_run_scan_requires_dast_run_permission(self, client):
        resp = client.post("/api/v1/dast-profiles/prof-1/run")
        assert resp.status_code in (401, 403)

    def test_patch_finding_requires_dast_triage_permission(self, client):
        resp = client.patch("/api/v1/findings/finding-1", json={"status": "triaged"})
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Group 9: Permission Catalog
# ---------------------------------------------------------------------------


class TestDastPermissions:
    def test_dast_group_in_catalog(self):
        from app.services.authz_service import PERMISSION_CATALOG

        groups = [g["group"].lower() for g in PERMISSION_CATALOG]
        assert "dast" in groups

    def test_dast_view_perm_exists(self):
        from app.services.authz_service import PERMISSION_CATALOG

        dast_group = next(g for g in PERMISSION_CATALOG if g["group"].lower() == "dast")
        assert "dast:view" in dast_group["perms"]

    def test_dast_run_perm_exists(self):
        from app.services.authz_service import PERMISSION_CATALOG

        dast_group = next(g for g in PERMISSION_CATALOG if g["group"].lower() == "dast")
        assert "dast:run" in dast_group["perms"]

    def test_dast_triage_perm_exists(self):
        from app.services.authz_service import PERMISSION_CATALOG

        dast_group = next(g for g in PERMISSION_CATALOG if g["group"].lower() == "dast")
        assert "dast:triage" in dast_group["perms"]

    def test_dast_configure_perm_exists(self):
        from app.services.authz_service import PERMISSION_CATALOG

        dast_group = next(g for g in PERMISSION_CATALOG if g["group"].lower() == "dast")
        assert "dast:configure" in dast_group["perms"]

    def test_dast_is_product_scoped(self):
        from app.services.authz_service import PERMISSION_CATALOG

        dast_group = next(g for g in PERMISSION_CATALOG if g["group"].lower() == "dast")
        assert dast_group.get("product_scoped") is True


# ---------------------------------------------------------------------------
# Group 10: Post-run Hook Integration
# ---------------------------------------------------------------------------


class TestDastPostRunHook:
    def test_dast_task_triggers_ingest(self):
        from app.services.run_service import _post_run_hooks

        mock_run = MagicMock()
        mock_task = MagicMock()
        mock_task.task_type = "dast"
        mock_task_run = MagicMock()
        mock_task_run.task = mock_task
        mock_task_run.output_json = json.dumps({"alerts": []})
        mock_task_run.agent_pool_id = "pool-zap"
        mock_stage_run = MagicMock()
        mock_stage_run.task_runs = [mock_task_run]
        mock_run.stage_runs = [mock_stage_run]
        mock_run.status = "Succeeded"

        with patch("app.services.run_service.dast_service") as mock_svc:
            mock_svc.ingest_findings.return_value = []
            _post_run_hooks(mock_run)
            mock_svc.ingest_findings.assert_called_once()

    def test_non_dast_task_not_processed(self):
        from app.services.run_service import _post_run_hooks

        mock_run = MagicMock()
        mock_task = MagicMock()
        mock_task.task_type = "build"
        mock_task_run = MagicMock()
        mock_task_run.task = mock_task
        mock_task_run.output_json = "{}"
        mock_stage_run = MagicMock()
        mock_stage_run.task_runs = [mock_task_run]
        mock_run.stage_runs = [mock_stage_run]
        mock_run.status = "Succeeded"

        with patch("app.services.run_service.dast_service") as mock_svc:
            _post_run_hooks(mock_run)
            mock_svc.ingest_findings.assert_not_called()

    def test_null_output_json_handled_gracefully(self):
        from app.services.run_service import _post_run_hooks

        mock_run = MagicMock()
        mock_task = MagicMock()
        mock_task.task_type = "dast"
        mock_task_run = MagicMock()
        mock_task_run.task = mock_task
        mock_task_run.output_json = None
        mock_stage_run = MagicMock()
        mock_stage_run.task_runs = [mock_task_run]
        mock_run.stage_runs = [mock_stage_run]
        mock_run.status = "Succeeded"

        with patch("app.services.run_service.dast_service"):
            _post_run_hooks(mock_run)  # must not raise
