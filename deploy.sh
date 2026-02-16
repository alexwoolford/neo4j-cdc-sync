#!/bin/bash
set -e  # Exit on any error
set -u  # Exit on undefined variables
set -o pipefail  # Catch errors in pipes

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print with color
print_error() { echo -e "${RED}✗ $1${NC}" >&2; }
print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ $1${NC}"; }

# Track if any issues found
PREFLIGHT_FAILED=0

echo "======================================================================"
echo "        Neo4j CDC Deployment - Pre-Flight Checks"
echo "======================================================================"
echo ""

# Check 1: Docker daemon running (conditional - only if using local builds)
if grep -q "docker build" terraform/modules/acr/main.tf 2>/dev/null; then
    print_info "Checking Docker daemon..."
    if docker info > /dev/null 2>&1; then
        print_success "Docker daemon is running"
    else
        print_error "Docker daemon is not running"
        print_info "Please start Docker Desktop and try again"
        print_info "Or switch to Azure-side builds (az acr build) to remove Docker dependency"
        PREFLIGHT_FAILED=1
    fi
else
    print_info "Using Azure ACR Tasks for builds (Docker not required)"
fi

# Check 2: Azure CLI authenticated
print_info "Checking Azure CLI authentication..."
if az account show > /dev/null 2>&1; then
    ACCOUNT=$(az account show --query name -o tsv)
    print_success "Azure CLI authenticated (Account: $ACCOUNT)"
else
    print_error "Azure CLI not authenticated"
    print_info "Run: az login"
    PREFLIGHT_FAILED=1
fi

# Check 3: Python environment and dependencies
print_info "Checking Python environment..."
if python3 -c "import rich, neo4j, requests" 2>/dev/null; then
    print_success "Python dependencies available (rich, neo4j, requests)"
else
    print_error "Python dependencies missing"
    print_info "Activate conda environment: conda activate neo4j-cdc-sync"
    print_info "Or create it: conda env create -f environment.yml"
    PREFLIGHT_FAILED=1
fi

# Check 4: Terraform installed
print_info "Checking Terraform..."
if command -v terraform > /dev/null 2>&1; then
    TF_VERSION=$(terraform version -json 2>/dev/null | python3 -c "import sys, json; print(json.load(sys.stdin)['terraform_version'])" 2>/dev/null || terraform version | head -1 | awk '{print $2}')
    print_success "Terraform installed (version $TF_VERSION)"
else
    print_error "Terraform not installed"
    print_info "Install from: https://developer.hashicorp.com/terraform/install"
    PREFLIGHT_FAILED=1
fi

# Check 5: terraform.tfvars exists
print_info "Checking Terraform configuration..."
if [ -f "terraform/terraform.tfvars" ]; then
    print_success "terraform.tfvars found"

    # Validate required variables are set (not empty)
    if grep -q "aura_client_id.*=" terraform/terraform.tfvars && \
       grep -q "aura_client_secret.*=" terraform/terraform.tfvars && \
       grep -q "aura_tenant_id.*=" terraform/terraform.tfvars; then

        # Check if values are not placeholder/empty
        if grep "aura_client_id" terraform/terraform.tfvars | grep -q "your-client-id\|^\s*aura_client_id\s*=\s*\"\"\s*$"; then
            print_error "Aura credentials appear to be placeholder values in terraform.tfvars"
            print_info "Edit terraform/terraform.tfvars and set aura_client_id, aura_client_secret, aura_tenant_id"
            print_info "Get credentials from: https://console.neo4j.io → Account → API Keys"
            PREFLIGHT_FAILED=1
        else
            print_success "Aura credentials configured in terraform.tfvars"
        fi
    else
        print_error "Aura credentials incomplete in terraform.tfvars"
        print_info "Edit terraform/terraform.tfvars and set aura_client_id, aura_client_secret, aura_tenant_id"
        print_info "Get credentials from: https://console.neo4j.io → Account → API Keys"
        PREFLIGHT_FAILED=1
    fi
else
    print_error "terraform.tfvars not found"
    print_info "Copy template: cp terraform/terraform.tfvars.example terraform/terraform.tfvars"
    print_info "Then edit and add your Aura API credentials"
    PREFLIGHT_FAILED=1
fi

echo ""

# Exit if pre-flight checks failed
if [ $PREFLIGHT_FAILED -eq 1 ]; then
    echo "======================================================================"
    print_error "Pre-flight checks failed. Please resolve issues above."
    echo "======================================================================"
    exit 1
fi

echo "======================================================================"
print_success "All pre-flight checks passed!"
echo "======================================================================"
echo ""

# Security warning before deployment
print_warning "SECURITY WARNING:"
echo "  This deployment exposes Kafka Connect REST API (port 8083) to the internet."
echo "  This is acceptable for short-term demos but NOT for production."
echo "  "
echo "  Anyone who finds your IP can:"
echo "    - Deploy malicious connectors"
echo "    - Read Event Hubs connection strings from connector configs"
echo "    - Potentially access your Neo4j instances"
echo "  "
echo "  Recommendation: Run 'terraform destroy' immediately after your demo."
echo "  "
read -p "Continue with deployment? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    print_info "Deployment cancelled by user"
    exit 0
fi

echo ""
print_info "Starting Terraform deployment..."
echo ""

# Deploy with Terraform
cd terraform

# Initialize (safe to run multiple times)
print_info "Initializing Terraform..."
terraform init

# Deploy
echo ""
print_info "Deploying infrastructure (this takes ~8 minutes)..."
echo ""

if terraform apply; then
    echo ""
    echo "======================================================================"
    print_success "Deployment completed successfully!"
    echo "======================================================================"
    echo ""
    print_info "Next steps:"
    echo "  1. Get credentials:"
    echo "     cd terraform && terraform output"
    echo "  "
    echo "  2. Test CDC:"
    echo "     cd terraform"
    echo "     export MASTER_NEO4J_URI=\$(terraform output -raw master_neo4j_uri)"
    echo "     export MASTER_NEO4J_PASSWORD=\$(terraform output -raw master_neo4j_password)"
    echo "     export SUBSCRIBER_NEO4J_URI=\$(terraform output -raw subscriber_neo4j_uri)"
    echo "     export SUBSCRIBER_NEO4J_PASSWORD=\$(terraform output -raw subscriber_neo4j_password)"
    echo "     cd ../python"
    echo "     python test_live_cdc.py"
    echo "  "
    echo "  3. Verify sync:"
    echo "     python verify_cdc.py"
    echo ""
    print_warning "IMPORTANT: Run 'terraform destroy' when done to avoid charges!"
    echo ""
    exit 0
else
    echo ""
    echo "======================================================================"
    print_error "Deployment failed!"
    echo "======================================================================"
    echo ""
    print_info "Common issues:"
    echo "  - Check Aura API credentials are correct"
    echo "  - Verify Azure subscription has sufficient quota"
    echo "  - Check terraform error output above for details"
    echo ""
    exit 1
fi
