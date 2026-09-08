.PHONY: security-scan
security-scan:
	trivy image --severity CRITICAL --exit-code 1 infra-api:latest
