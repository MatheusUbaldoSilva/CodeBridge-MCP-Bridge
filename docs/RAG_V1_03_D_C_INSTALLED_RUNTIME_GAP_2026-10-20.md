# V1.03-D-C — Installed runtime divergence audit

Date: 2026-10-20
Scope: read-only inspection, NO automatic runtime update

Repository source:
- installer/CodeBridge.nsi packages rag Python sources
- requirements.txt declares qdrant-client==1.19.1
- installer/bootstrap.ps1 writes embedded Python _pth with ..\\.. and installs requirements

Observed installed runtime:
- CodeBridge embedded Python path: Programs/CodeBridge/runtime/python/python.exe
- python313._pth missing ..\\.. root import path
- qdrant_client import unavailable in embedded runtime
- rag package import unavailable in embedded runtime
- standalone system Python can run actual real-Jina staging worker and subprocess/restart E2E successfully

Interpretation:
The installed artifact does not match the latest repository bootstrap/dependency contract.
This is a DEPLOYMENT gap, not evidence that the offline Jina worker or persistent receipt failed.
Do not modify installed Python paths or pip packages ad hoc.
Next step: controlled installed runtime updater/bootstrap dry-run and dependency validation,
then targeted E2E from embedded runtime before declaring installed V1.03-D-C ready.
No public index mutation, service stop, scheduler or permanent cutover is authorized.
