#!/usr/bin/env bash
# One-time migration: remove all users from Cognito groups before deleting groups via Terraform.
# Run this BEFORE running `terraform apply` that removes the group resources.
#
# Usage:
#   AWS_PROFILE=your-profile bash scripts/migrate-remove-cognito-groups.sh <USER_POOL_ID>

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <USER_POOL_ID>"
  exit 1
fi

USER_POOL_ID="$1"
GROUPS=("L1-operator" "L2-engineer" "L3-admin")

for GROUP in "${GROUPS[@]}"; do
  echo "Processing group: $GROUP"

  # List all users in the group
  USERS=$(aws cognito-idp list-users-in-group \
    --user-pool-id "$USER_POOL_ID" \
    --group-name "$GROUP" \
    --query 'Users[].Username' \
    --output text 2>/dev/null || true)

  if [ -z "$USERS" ]; then
    echo "  No users in group $GROUP (or group does not exist). Skipping."
    continue
  fi

  for USERNAME in $USERS; do
    echo "  Removing $USERNAME from $GROUP"
    aws cognito-idp admin-remove-user-from-group \
      --user-pool-id "$USER_POOL_ID" \
      --username "$USERNAME" \
      --group-name "$GROUP"
  done
done

echo ""
echo "Done. All users have been removed from Cognito groups."
echo "You can now safely run 'terraform apply' to delete the group resources."
