#!/usr/bin/env bash
set -euo pipefail

INFRA_DIR="$(cd "$(dirname "$0")/../../infra" && pwd)"
ERRORS=0

echo "=== Terraform Format Check ==="
if ! terraform -chdir="$INFRA_DIR" fmt -check -recursive -diff; then
    echo "FAIL: Terraform files not formatted. Run: terraform fmt -recursive infra/"
    ERRORS=$((ERRORS + 1))
else
    echo "PASS: All .tf files formatted correctly"
fi

echo ""
echo "=== Terraform Validate ==="
# Create placeholder.zip if missing (normally built by CI/deploy scripts)
PLACEHOLDER="$INFRA_DIR/modules/lambdas/placeholder.zip"
CREATED_PLACEHOLDER=false
if [ ! -f "$PLACEHOLDER" ]; then
    echo "(creating placeholder.zip for validation)"
    echo "placeholder" | zip -q "$PLACEHOLDER" -
    CREATED_PLACEHOLDER=true
fi
terraform -chdir="$INFRA_DIR" init -backend=false -input=false > /dev/null 2>&1
if ! terraform -chdir="$INFRA_DIR" validate; then
    echo "FAIL: Terraform validation errors"
    ERRORS=$((ERRORS + 1))
else
    echo "PASS: Terraform configuration valid"
fi
if [ "$CREATED_PLACEHOLDER" = true ]; then
    rm -f "$PLACEHOLDER"
fi

echo ""
echo "=== Module Structure Check ==="
EXPECTED_MODULES="api cognito hosting lambdas storage"
for mod in $EXPECTED_MODULES; do
    if [ ! -f "$INFRA_DIR/modules/$mod/main.tf" ]; then
        echo "FAIL: Missing module $mod"
        ERRORS=$((ERRORS + 1))
    else
        echo "PASS: Module $mod exists"
    fi
done

echo ""
echo "=== tfsec Security Scan ==="
if command -v tfsec &> /dev/null; then
    if ! tfsec "$INFRA_DIR" --minimum-severity MEDIUM --format text; then
        echo "WARN: tfsec found issues (non-blocking)"
    else
        echo "PASS: tfsec found no medium+ severity issues"
    fi
else
    echo "SKIP: tfsec not installed. Install with: curl -s https://raw.githubusercontent.com/aquasecurity/tfsec/master/scripts/install_linux.sh | bash"
fi

echo ""
if [ $ERRORS -gt 0 ]; then
    echo "=== $ERRORS check(s) failed ==="
    exit 1
else
    echo "=== All infrastructure checks passed ==="
fi
