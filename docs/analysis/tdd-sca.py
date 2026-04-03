"""
TDD Test Cases — SCA Capability
Derived from: docs/analysis/sca-capability-analysis.md

Run with: pytest docs/analysis/tdd-sca.py -v
These are specification tests — they define the expected contract BEFORE implementation.
All tests will fail until the corresponding code is written.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def pip_audit_output_single():
    """Minimal pip-audit JSON with one CVE."""
    return json.dumps(
        {
            "dependencies": [
                {
                    "name": "requests",
                    "version": "2.20.0",
                    "vulns": [
                        {
                            "id": "PYSEC-2023-74",
                            "fix_versions": ["2.31.0"],
                            "aliases": ["CVE-2023-32681"],
                            "description": "Requests forwards proxy-authorization headers.",
                        }
                    ],
                }
            ]
        }
    )


@pytest.fixture
def pip_audit_output_multi():
    """pip-audit JSON with multiple packages and severities."""
    return json.dumps(
        {
            "dependencies": [
                {
                    "name": "cryptography",
                    "version": "38.0.0",
                    "vulns": [
                        {
                            "id": "PYSEC-2023-1",
                            "fix_versions": ["41.0.0"],
                            "aliases": ["CVE-2023-49083"],
                            "description": "NULL pointer dereference in PKCS12.",
                        },
                        {
                            "id": "PYSEC-2023-2",
                            "fix_versions": ["41.0.2"],
                            "aliases": ["CVE-2023-23931"],
                            "description": "Memory corruption via Bleichenbacher oracle.",
                        },
                    ],
                },
                {
                    "name": "pillow",
                    "version": "9.0.0",
                    "vulns": [
                        {
                            "id": "PYSEC-2023-3",
                            "fix_versions": ["9.3.0"],
                            "aliases": ["CVE-2023-44271"],
                            "description": "Uncontrolled resource consumption in ImageFont.",
                        }
                    ],
                },
                {
                    "name": "flask",
                    "version": "2.3.0",
                    "vulns": [],
                },
            ]
        }
    )


@pytest.fixture
def pip_audit_output_empty():
    """pip-audit JSON with no vulnerabilities."""
    return json.dumps({"dependencies": []})


@pytest.fixture
def safety_output_single():
    """safety check --json output with one finding."""
    return json.dumps(
        [
            [
                "django",
                "<2.2.24",
                "2.1.0",
                "Django before 2.2.24 allows potential SQL injection.",
                "CVE-2021-31542",
                "44742",
            ]
        ]
    )


@pytest.fixture
def safety_output_empty():
    return json.dumps([])


@pytest.fixture
def mock_app_id():
    return "app-abc-123"


@pytest.fixture
def mock_product_id():
    return "prod-xyz-456"


# ---------------------------------------------------------------------------
# Group 1: parse_pip_audit_output
# ---------------------------------------------------------------------------


class TestParsePipAuditOutput:
    def test_single_vuln_returns_one_finding(self, pip_audit_output_single):
        from app.services.python_sca_service import parse_pip_audit_output

        findings = parse_pip_audit_output(pip_audit_output_single)
        assert len(findings) == 1

    def test_finding_has_required_fields(self, pip_audit_output_single):
        from app.services.python_sca_service import parse_pip_audit_output

        finding = parse_pip_audit_output(pip_audit_output_single)[0]
        assert finding["package_name"] == "requests"
        assert finding["package_version"] == "2.20.0"
        assert finding["cve_id"] == "CVE-2023-32681"
        assert finding["fixed_in_version"] == "2.31.0"
        assert "description" in finding

    def test_multi_package_multi_vuln(self, pip_audit_output_multi):
        from app.services.python_sca_service import parse_pip_audit_output

        findings = parse_pip_audit_output(pip_audit_output_multi)
        # cryptography has 2 vulns, pillow has 1, flask has 0 → total 3
        assert len(findings) == 3

    def test_package_with_no_vulns_excluded(self, pip_audit_output_multi):
        from app.services.python_sca_service import parse_pip_audit_output

        findings = parse_pip_audit_output(pip_audit_output_multi)
        names = [f["package_name"] for f in findings]
        assert "flask" not in names

    def test_empty_output_returns_empty_list(self, pip_audit_output_empty):
        from app.services.python_sca_service import parse_pip_audit_output

        assert parse_pip_audit_output(pip_audit_output_empty) == []

    def test_malformed_json_raises_value_error(self):
        from app.services.python_sca_service import parse_pip_audit_output

        with pytest.raises((ValueError, json.JSONDecodeError)):
            parse_pip_audit_output("not-json{{{")

    def test_missing_dependencies_key_raises(self):
        from app.services.python_sca_service import parse_pip_audit_output

        with pytest.raises((ValueError, KeyError)):
            parse_pip_audit_output(json.dumps({"results": []}))

    def test_scanner_tool_set_to_pip_audit(self, pip_audit_output_single):
        from app.services.python_sca_service import parse_pip_audit_output

        finding = parse_pip_audit_output(pip_audit_output_single)[0]
        assert finding["scanner_tool"] == "pip-audit"

    def test_cve_id_prefers_cve_alias_over_pysec(self, pip_audit_output_single):
        from app.services.python_sca_service import parse_pip_audit_output

        finding = parse_pip_audit_output(pip_audit_output_single)[0]
        # Should prefer CVE-XXXX-XXXX over PYSEC-XXXX-XX
        assert finding["cve_id"].startswith("CVE-")

    def test_no_fix_version_sets_none(self):
        from app.services.python_sca_service import parse_pip_audit_output

        raw = json.dumps(
            {
                "dependencies": [
                    {
                        "name": "pkg",
                        "version": "1.0.0",
                        "vulns": [
                            {
                                "id": "PYSEC-1",
                                "fix_versions": [],
                                "aliases": [],
                                "description": "desc",
                            }
                        ],
                    }
                ]
            }
        )
        finding = parse_pip_audit_output(raw)[0]
        assert finding["fixed_in_version"] is None


# ---------------------------------------------------------------------------
# Group 2: parse_safety_output
# ---------------------------------------------------------------------------


class TestParseSafetyOutput:
    def test_single_finding_parsed(self, safety_output_single):
        from app.services.python_sca_service import parse_safety_output

        findings = parse_safety_output(safety_output_single)
        assert len(findings) == 1

    def test_finding_fields_correct(self, safety_output_single):
        from app.services.python_sca_service import parse_safety_output

        finding = parse_safety_output(safety_output_single)[0]
        assert finding["package_name"] == "django"
        assert finding["cve_id"] == "CVE-2021-31542"
        assert finding["scanner_tool"] == "safety"

    def test_empty_output_returns_empty(self, safety_output_empty):
        from app.services.python_sca_service import parse_safety_output

        assert parse_safety_output(safety_output_empty) == []

    def test_malformed_json_raises(self):
        from app.services.python_sca_service import parse_safety_output

        with pytest.raises((ValueError, json.JSONDecodeError)):
            parse_safety_output("INVALID")

    def test_missing_cve_id_still_creates_finding(self):
        from app.services.python_sca_service import parse_safety_output

        raw = json.dumps([["pkg", "<2.0", "1.0", "Description", "", "12345"]])
        findings = parse_safety_output(raw)
        assert len(findings) == 1
        assert findings[0]["cve_id"] is None or findings[0]["cve_id"] == ""


# ---------------------------------------------------------------------------
# Group 3: record_vulnerabilities
# ---------------------------------------------------------------------------


class TestRecordVulnerabilities:
    def test_happy_path_inserts_rows(self, mock_app_id):
        from app.services.python_sca_service import record_vulnerabilities

        findings = [
            {
                "package_name": "requests",
                "package_version": "2.20.0",
                "cve_id": "CVE-2023-32681",
                "severity": "HIGH",
                "cvss_score": 6.1,
                "description": "Desc",
                "fixed_in_version": "2.31.0",
                "scanner_tool": "pip-audit",
                "sbom_json": None,
            }
        ]
        with patch("app.services.python_sca_service.db") as mock_db:
            mock_db.session.add = MagicMock()
            mock_db.session.commit = MagicMock()
            record_vulnerabilities(mock_app_id, findings, "pip-audit")
            assert mock_db.session.add.call_count == 1
            assert mock_db.session.commit.called

    def test_duplicate_cve_for_same_package_upserts(self, mock_app_id):
        from app.services.python_sca_service import record_vulnerabilities

        findings = [
            {
                "package_name": "requests",
                "package_version": "2.20.0",
                "cve_id": "CVE-2023-32681",
                "severity": "HIGH",
                "cvss_score": 6.1,
                "description": "Desc",
                "fixed_in_version": "2.31.0",
                "scanner_tool": "pip-audit",
                "sbom_json": None,
            }
        ]
        with patch("app.services.python_sca_service.db") as mock_db:
            with patch(
                "app.services.python_sca_service.PythonDependencyVulnerability"
            ) as mock_model:
                existing = MagicMock()
                mock_model.query.filter_by.return_value.first.return_value = existing
                record_vulnerabilities(mock_app_id, findings, "pip-audit")
                # Should update existing, not create new
                assert mock_db.session.add.call_count == 0

    def test_empty_findings_no_db_calls(self, mock_app_id):
        from app.services.python_sca_service import record_vulnerabilities

        with patch("app.services.python_sca_service.db") as mock_db:
            record_vulnerabilities(mock_app_id, [], "pip-audit")
            assert not mock_db.session.commit.called

    def test_returns_count_of_records_written(self, mock_app_id):
        from app.services.python_sca_service import record_vulnerabilities

        findings = [
            {
                "package_name": f"pkg{i}",
                "package_version": "1.0.0",
                "cve_id": f"CVE-2023-{i:05d}",
                "severity": "HIGH",
                "cvss_score": 7.0,
                "description": "D",
                "fixed_in_version": None,
                "scanner_tool": "pip-audit",
                "sbom_json": None,
            }
            for i in range(3)
        ]
        with patch("app.services.python_sca_service.db"):
            with patch(
                "app.services.python_sca_service.PythonDependencyVulnerability"
            ) as mock_model:
                mock_model.query.filter_by.return_value.first.return_value = None
                count = record_vulnerabilities(mock_app_id, findings, "pip-audit")
                assert count == 3


# ---------------------------------------------------------------------------
# Group 4: get_vulnerabilities
# ---------------------------------------------------------------------------


class TestGetVulnerabilities:
    def test_returns_all_by_default(self, mock_app_id):
        from app.services.python_sca_service import get_vulnerabilities

        with patch("app.services.python_sca_service.PythonDependencyVulnerability") as mock_model:
            mock_model.query.filter_by.return_value.all.return_value = [MagicMock(), MagicMock()]
            results = get_vulnerabilities(mock_app_id)
            assert len(results) == 2

    def test_severity_filter_applied(self, mock_app_id):
        from app.services.python_sca_service import get_vulnerabilities

        with patch("app.services.python_sca_service.PythonDependencyVulnerability") as mock_model:
            mock_query = MagicMock()
            mock_model.query.filter_by.return_value = mock_query
            mock_query.filter.return_value.all.return_value = []
            get_vulnerabilities(mock_app_id, severity_min="HIGH")
            mock_query.filter.assert_called_once()

    def test_unknown_app_returns_empty(self):
        from app.services.python_sca_service import get_vulnerabilities

        with patch("app.services.python_sca_service.PythonDependencyVulnerability") as mock_model:
            mock_model.query.filter_by.return_value.all.return_value = []
            assert get_vulnerabilities("nonexistent-app") == []

    def test_severity_order_critical_high_medium_low(self, mock_app_id):
        """Severity filtering must respect: CRITICAL > HIGH > MEDIUM > LOW."""
        from app.services.python_sca_service import get_vulnerabilities

        SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
        for sev in SEVERITY_ORDER:
            with patch("app.services.python_sca_service.PythonDependencyVulnerability"):
                # Should not raise — valid severity values accepted
                get_vulnerabilities(mock_app_id, severity_min=sev)

    def test_invalid_severity_raises(self, mock_app_id):
        from app.services.python_sca_service import get_vulnerabilities

        with pytest.raises(ValueError):
            get_vulnerabilities(mock_app_id, severity_min="EXTREME")


# ---------------------------------------------------------------------------
# Group 5: get_product_vulnerability_summary
# ---------------------------------------------------------------------------


class TestGetProductVulnerabilitySummary:
    def test_aggregates_counts_by_severity(self, mock_product_id):
        from app.services.python_sca_service import get_product_vulnerability_summary

        with patch("app.services.python_sca_service.PythonDependencyVulnerability") as mock_model:
            mock_rows = [
                MagicMock(severity="CRITICAL"),
                MagicMock(severity="HIGH"),
                MagicMock(severity="HIGH"),
                MagicMock(severity="MEDIUM"),
            ]
            mock_model.query.join.return_value.filter.return_value.all.return_value = mock_rows
            summary = get_product_vulnerability_summary(mock_product_id)
            assert summary["critical"] == 1
            assert summary["high"] == 2
            assert summary["medium"] == 1
            assert summary["low"] == 0

    def test_empty_product_returns_zero_counts(self, mock_product_id):
        from app.services.python_sca_service import get_product_vulnerability_summary

        with patch("app.services.python_sca_service.PythonDependencyVulnerability") as mock_model:
            mock_model.query.join.return_value.filter.return_value.all.return_value = []
            summary = get_product_vulnerability_summary(mock_product_id)
            assert summary["critical"] == 0
            assert summary["high"] == 0
            assert summary["total"] == 0

    def test_summary_includes_total_count(self, mock_product_id):
        from app.services.python_sca_service import get_product_vulnerability_summary

        with patch("app.services.python_sca_service.PythonDependencyVulnerability") as mock_model:
            mock_model.query.join.return_value.filter.return_value.all.return_value = [
                MagicMock(severity="HIGH") for _ in range(5)
            ]
            summary = get_product_vulnerability_summary(mock_product_id)
            assert summary["total"] == 5


# ---------------------------------------------------------------------------
# Group 6: generate_sbom
# ---------------------------------------------------------------------------


class TestGenerateSbom:
    def test_returns_cyclonedx_structure(self, mock_app_id, tmp_path):
        from app.services.python_sca_service import generate_sbom

        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests==2.31.0\n")
        mock_sbom = {
            "bomFormat": "CycloneDX",
            "specVersion": "1.4",
            "components": [{"name": "requests", "version": "2.31.0"}],
        }
        with patch("app.services.python_sca_service.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(mock_sbom))
            result = generate_sbom(mock_app_id, str(req_file))
            assert result["bomFormat"] == "CycloneDX"

    def test_subprocess_failure_raises(self, mock_app_id, tmp_path):
        from app.services.python_sca_service import generate_sbom

        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests==2.31.0\n")
        with patch("app.services.python_sca_service.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="error")
            with pytest.raises(RuntimeError):
                generate_sbom(mock_app_id, str(req_file))

    def test_missing_requirements_file_raises(self, mock_app_id):
        from app.services.python_sca_service import generate_sbom

        with pytest.raises((FileNotFoundError, ValueError)):
            generate_sbom(mock_app_id, "/nonexistent/requirements.txt")


# ---------------------------------------------------------------------------
# Group 7: API Routes (Flask test client)
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
    """Obtain JWT token for admin user."""
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
    token = resp.get_json().get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


class TestVulnerabilityRoutes:
    def test_scan_endpoint_returns_202(self, client, auth_headers, mock_app_id, mock_product_id):
        """POST /scan triggers asynchronous scan and returns 202 Accepted."""
        with patch("app.routes.vulnerabilities.python_sca_service.scan_requirements") as mock_scan:
            mock_scan.return_value = []
            resp = client.post(
                f"/api/v1/products/{mock_product_id}/applications/{mock_app_id}/scan",
                headers=auth_headers,
            )
            assert resp.status_code in (200, 202)

    def test_list_vulnerabilities_returns_200(
        self, client, auth_headers, mock_app_id, mock_product_id
    ):
        with patch("app.routes.vulnerabilities.python_sca_service.get_vulnerabilities") as mock_get:
            mock_get.return_value = []
            resp = client.get(
                f"/api/v1/products/{mock_product_id}/applications/{mock_app_id}/vulnerabilities",
                headers=auth_headers,
            )
            assert resp.status_code == 200

    def test_list_vulnerabilities_severity_filter(
        self, client, auth_headers, mock_app_id, mock_product_id
    ):
        with patch("app.routes.vulnerabilities.python_sca_service.get_vulnerabilities") as mock_get:
            mock_get.return_value = []
            resp = client.get(
                f"/api/v1/products/{mock_product_id}/applications/{mock_app_id}/vulnerabilities?severity=HIGH",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            mock_get.assert_called_once_with(mock_app_id, severity_min="HIGH")

    def test_product_summary_endpoint(self, client, auth_headers, mock_product_id):
        with patch(
            "app.routes.vulnerabilities.python_sca_service.get_product_vulnerability_summary"
        ) as mock_summ:
            mock_summ.return_value = {"critical": 0, "high": 1, "medium": 2, "low": 3, "total": 6}
            resp = client.get(
                f"/api/v1/products/{mock_product_id}/vulnerabilities",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert "total" in data

    def test_sbom_endpoint_returns_cyclonedx(
        self, client, auth_headers, mock_app_id, mock_product_id
    ):
        with patch("app.routes.vulnerabilities.python_sca_service.generate_sbom") as mock_sbom:
            mock_sbom.return_value = {"bomFormat": "CycloneDX", "components": []}
            resp = client.get(
                f"/api/v1/products/{mock_product_id}/applications/{mock_app_id}/sbom",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            assert resp.get_json()["bomFormat"] == "CycloneDX"

    def test_delete_clears_findings(self, client, auth_headers, mock_app_id, mock_product_id):
        with patch("app.routes.vulnerabilities.python_sca_service") as mock_svc:
            mock_svc.clear_vulnerabilities = MagicMock()
            resp = client.delete(
                f"/api/v1/products/{mock_product_id}/applications/{mock_app_id}/vulnerabilities",
                headers=auth_headers,
            )
            assert resp.status_code in (200, 204)

    def test_scan_requires_authentication(self, client, mock_app_id, mock_product_id):
        resp = client.post(f"/api/v1/products/{mock_product_id}/applications/{mock_app_id}/scan")
        assert resp.status_code in (401, 403)

    def test_list_requires_authentication(self, client, mock_app_id, mock_product_id):
        resp = client.get(
            f"/api/v1/products/{mock_product_id}/applications/{mock_app_id}/vulnerabilities"
        )
        assert resp.status_code in (401, 403)

    def test_invalid_severity_query_param_returns_400(
        self, client, auth_headers, mock_app_id, mock_product_id
    ):
        resp = client.get(
            f"/api/v1/products/{mock_product_id}/applications/{mock_app_id}/vulnerabilities?severity=EXTREME",
            headers=auth_headers,
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Group 8: Run Hook Integration
# ---------------------------------------------------------------------------


class TestRunHookIntegration:
    def test_sca_task_run_triggers_record(self):
        """_post_run_hooks() must call record_vulnerabilities for sca task runs."""
        from app.services.run_service import _post_run_hooks

        mock_run = MagicMock()
        mock_task = MagicMock()
        mock_task.task_type = "sca"
        mock_task_run = MagicMock()
        mock_task_run.task = mock_task
        mock_task_run.output_json = json.dumps({"dependencies": []})
        mock_stage_run = MagicMock()
        mock_stage_run.task_runs = [mock_task_run]
        mock_run.stage_runs = [mock_stage_run]
        mock_run.status = "Succeeded"

        with patch("app.services.run_service.python_sca_service") as mock_svc:
            mock_svc.parse_pip_audit_output.return_value = []
            mock_svc.record_vulnerabilities.return_value = 0
            _post_run_hooks(mock_run)
            mock_svc.record_vulnerabilities.assert_called_once()

    def test_non_sca_task_run_not_processed(self):
        """_post_run_hooks() must NOT call record_vulnerabilities for non-sca tasks."""
        from app.services.run_service import _post_run_hooks

        mock_run = MagicMock()
        mock_task = MagicMock()
        mock_task.task_type = "build"
        mock_task_run = MagicMock()
        mock_task_run.task = mock_task
        mock_task_run.output_json = '{"key": "value"}'
        mock_stage_run = MagicMock()
        mock_stage_run.task_runs = [mock_task_run]
        mock_run.stage_runs = [mock_stage_run]
        mock_run.status = "Succeeded"

        with patch("app.services.run_service.python_sca_service") as mock_svc:
            _post_run_hooks(mock_run)
            mock_svc.record_vulnerabilities.assert_not_called()

    def test_null_output_json_skipped_gracefully(self):
        """No crash when task_run.output_json is None."""
        from app.services.run_service import _post_run_hooks

        mock_run = MagicMock()
        mock_task = MagicMock()
        mock_task.task_type = "sca"
        mock_task_run = MagicMock()
        mock_task_run.task = mock_task
        mock_task_run.output_json = None
        mock_stage_run = MagicMock()
        mock_stage_run.task_runs = [mock_task_run]
        mock_run.stage_runs = [mock_stage_run]
        mock_run.status = "Succeeded"

        with patch("app.services.run_service.python_sca_service") as mock_svc:
            _post_run_hooks(mock_run)  # must not raise
            mock_svc.record_vulnerabilities.assert_not_called()

    def test_critical_cve_updates_compliance_rating(self):
        """Presence of CRITICAL CVE after scan must lower ApplicationArtifact.compliance_rating."""
        from app.services.run_service import _post_run_hooks

        mock_run = MagicMock()
        mock_task = MagicMock()
        mock_task.task_type = "sca"
        mock_task_run = MagicMock()
        mock_task_run.task = mock_task
        mock_task_run.output_json = json.dumps({"dependencies": []})
        mock_stage_run = MagicMock()
        mock_stage_run.task_runs = [mock_task_run]
        mock_run.stage_runs = [mock_stage_run]
        mock_run.status = "Succeeded"

        with patch("app.services.run_service.python_sca_service") as mock_svc:
            mock_svc.parse_pip_audit_output.return_value = [
                {"severity": "CRITICAL", "cve_id": "CVE-2023-1234", "package_name": "pkg"}
            ]
            mock_svc.record_vulnerabilities.return_value = 1
            with patch("app.services.run_service.db") as mock_db:
                _post_run_hooks(mock_run)
                # compliance_rating update must be committed
                assert mock_db.session.commit.called


# ---------------------------------------------------------------------------
# Group 9: Permission / AuthZ
# ---------------------------------------------------------------------------


class TestScaPermissions:
    def test_vulnerabilities_view_in_catalog(self):
        from app.services.authz_service import PERMISSION_CATALOG

        groups = {g["group"].lower() for g in PERMISSION_CATALOG}
        assert "vulnerabilities" in groups or "sca" in groups

    def test_vulnerabilities_scan_permission_exists(self):
        from app.services.authz_service import PERMISSION_CATALOG

        perms = []
        for g in PERMISSION_CATALOG:
            perms.extend(g.get("perms", []))
        assert any("scan" in p for p in perms)

    def test_vulnerabilities_view_permission_exists(self):
        from app.services.authz_service import PERMISSION_CATALOG

        perms = []
        for g in PERMISSION_CATALOG:
            perms.extend(g.get("perms", []))
        assert any("view" in p for p in perms)
