#!/bin/bash
# CommandBridge Deployment Script
# Single command deploys everything: infrastructure + portal

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
AWS_REGION=${AWS_REGION:-eu-west-2}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
INFRA_DIR="$ROOT_DIR/infra"
LAMBDAS_DIR="$ROOT_DIR/lambdas"
FRONTEND_DIR="$ROOT_DIR/frontend"
SITE_DIR="$ROOT_DIR/site"

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}CommandBridge Deployment${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# Status helpers
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${YELLOW}ℹ${NC} $1"
}

# ============================================
# Build React Frontend
# ============================================
echo -e "${BLUE}[1/5] Building React frontend...${NC}"

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    print_info "Installing dependencies..."
    (cd "$FRONTEND_DIR" && npm ci --silent) || {
        print_error "npm ci failed"
        exit 1
    }
fi

(cd "$FRONTEND_DIR" && npm run build) || {
    print_error "Frontend build failed"
    exit 1
}

print_status "React frontend built"
echo ""

# ============================================
# Package Lambda
# ============================================
echo -e "${BLUE}[2/5] Packaging Lambda function...${NC}"

LAMBDA_ZIP="$INFRA_DIR/modules/lambdas/placeholder.zip"
TEMP_DIR=$(mktemp -d)

cp -r "$LAMBDAS_DIR/actions/"* "$TEMP_DIR/"
cp -r "$LAMBDAS_DIR/shared" "$TEMP_DIR/shared"
mkdir -p "$TEMP_DIR/rbac"
cp "$ROOT_DIR/rbac/actions.json" "$TEMP_DIR/rbac/actions.json"

(cd "$TEMP_DIR" && zip -qr "$LAMBDA_ZIP" .) || {
    print_error "Lambda packaging failed"
    rm -rf "$TEMP_DIR"
    exit 1
}
rm -rf "$TEMP_DIR"

print_status "Lambda packaged ($LAMBDA_ZIP)"
echo ""

# ============================================
# Terraform Apply
# ============================================
echo -e "${BLUE}[3/5] Applying Terraform changes...${NC}"

print_info "Initialising Terraform..."
terraform -chdir="$INFRA_DIR" init -input=false > /dev/null 2>&1 || {
    print_error "Terraform init failed"
    exit 1
}

terraform -chdir="$INFRA_DIR" apply -auto-approve || {
    print_error "Terraform apply failed"
    exit 1
}

print_status "Infrastructure updated (Cognito, Lambda, API Gateway, DynamoDB, CloudFront)"
echo ""

# ============================================
# Deploy Portal to S3
# ============================================
echo -e "${BLUE}[4/5] Deploying portal to S3...${NC}"

BUCKET=$(terraform -chdir="$INFRA_DIR" output -raw s3_bucket 2>/dev/null || echo "")
CLOUDFRONT_DIST=$(terraform -chdir="$INFRA_DIR" output -raw cloudfront_distribution_id 2>/dev/null || echo "")

if [ -z "$BUCKET" ]; then
    print_error "Could not get S3 bucket name from Terraform"
    exit 1
fi

print_info "Syncing portal to s3://$BUCKET..."

# Upload HTML with no-cache (SPA entry points)
for html_file in "$SITE_DIR"/*.html; do
    [ -f "$html_file" ] || continue
    aws s3 cp "$html_file" "s3://$BUCKET/$(basename "$html_file")" \
        --cache-control "no-cache, no-store, must-revalidate" \
        --content-type "text/html" \
        --region "$AWS_REGION" \
        --no-cli-pager > /dev/null
done

# Upload static assets with long cache
aws s3 sync "$SITE_DIR" "s3://$BUCKET" \
    --delete \
    --exclude "*.html" \
    --cache-control "max-age=31536000, public, immutable" \
    --region "$AWS_REGION" \
    --no-progress

print_status "Portal deployed to s3://$BUCKET"
echo ""

# ============================================
# Invalidate CloudFront
# ============================================
echo -e "${BLUE}[5/5] Invalidating CloudFront cache...${NC}"

if [ -n "$CLOUDFRONT_DIST" ]; then
    aws cloudfront create-invalidation \
        --distribution-id "$CLOUDFRONT_DIST" \
        --paths "/*" \
        --region "$AWS_REGION" \
        --no-cli-pager > /dev/null || true
    print_status "Cache invalidation submitted"
else
    print_info "No distribution ID found, skipping"
fi

echo ""

# ============================================
# Summary
# ============================================
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}================================${NC}"

PORTAL_URL="https://$(terraform -chdir="$INFRA_DIR" output -raw cloudfront_domain 2>/dev/null || echo "pending")"
API_URL=$(terraform -chdir="$INFRA_DIR" output -raw api_gateway_url 2>/dev/null || echo "pending")
COGNITO_URL=$(terraform -chdir="$INFRA_DIR" output -raw cognito_domain 2>/dev/null || echo "pending")

echo ""
echo -e "Portal:   ${BLUE}${PORTAL_URL}${NC}"
echo -e "API:      ${BLUE}${API_URL}${NC}"
echo -e "Cognito:  ${BLUE}${COGNITO_URL}${NC}"
echo -e "S3:       ${BLUE}s3://${BUCKET}${NC}"
echo ""
echo -e "${GREEN}✓${NC} All infrastructure and code deployed successfully"
echo ""
