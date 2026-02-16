#!/usr/bin/env python3
"""
Pre-flight checks for Neo4j CDC deployment.

Validates prerequisites before running terraform apply:
- Azure CLI authentication
- Python dependencies
- Terraform configuration (terraform.tfvars with Aura credentials)

Usage:
    python preflight.py

Exit codes:
    0 - All checks passed
    1 - One or more checks failed
"""

import subprocess
import sys
from pathlib import Path

from rich.console import Console

console = Console()


def check_azure_cli() -> bool:
    """Check if Azure CLI is authenticated."""
    console.print("[blue]Checking Azure CLI authentication...[/blue]")
    try:
        result = subprocess.run(
            ["az", "account", "show", "--query", "name", "-o", "tsv"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            console.print(f"[green]✓ Azure CLI authenticated (Account: {result.stdout.strip()})[/green]")
            return True
        else:
            console.print("[red]✗ Azure CLI not authenticated[/red]")
            console.print("[dim]  Run: az login[/dim]")
            return False
    except FileNotFoundError:
        console.print("[red]✗ Azure CLI not installed[/red]")
        console.print("[dim]  Install from: https://learn.microsoft.com/cli/azure/install-azure-cli[/dim]")
        return False
    except subprocess.TimeoutExpired:
        console.print("[red]✗ Azure CLI timed out[/red]")
        return False


def check_python_dependencies() -> bool:
    """Check if required Python packages are available."""
    console.print("[blue]Checking Python dependencies...[/blue]")
    required = ["rich", "neo4j", "requests"]
    missing = []

    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if not missing:
        console.print(f"[green]✓ Python dependencies available ({', '.join(required)})[/green]")
        return True
    else:
        console.print(f"[red]✗ Missing Python packages: {', '.join(missing)}[/red]")
        console.print("[dim]  Activate conda environment: conda activate neo4j-cdc-sync[/dim]")
        console.print("[dim]  Or create it: conda env create -f environment.yml[/dim]")
        return False


def check_terraform_config() -> bool:
    """Check if terraform.tfvars exists and has Aura credentials."""
    console.print("[blue]Checking Terraform configuration...[/blue]")

    # Find terraform.tfvars relative to this script or repo root
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    tfvars_path = repo_root / "terraform" / "terraform.tfvars"

    if not tfvars_path.exists():
        console.print("[red]✗ terraform/terraform.tfvars not found[/red]")
        console.print("[dim]  Copy template: cp terraform/terraform.tfvars.example terraform/terraform.tfvars[/dim]")
        console.print("[dim]  Then edit and add your Aura API credentials[/dim]")
        return False

    # Check for required Aura credentials
    content = tfvars_path.read_text()
    required_vars = ["aura_client_id", "aura_client_secret", "aura_tenant_id"]
    missing = []
    placeholder = []

    for var in required_vars:
        if var not in content:
            missing.append(var)
        elif f'{var} = ""' in content or "your-client-id" in content:
            placeholder.append(var)

    if missing:
        console.print(f"[red]✗ Missing variables in terraform.tfvars: {', '.join(missing)}[/red]")
        return False

    if placeholder:
        console.print("[red]✗ Aura credentials appear to be placeholder values[/red]")
        console.print("[dim]  Edit terraform/terraform.tfvars and set actual values[/dim]")
        console.print("[dim]  Get credentials from: https://console.neo4j.io → Account → API Keys[/dim]")
        return False

    console.print("[green]✓ terraform.tfvars found with Aura credentials[/green]")
    return True


def check_terraform_installed() -> bool:
    """Check if Terraform is installed."""
    console.print("[blue]Checking Terraform...[/blue]")
    try:
        result = subprocess.run(
            ["terraform", "version", "-json"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            import json
            try:
                version_info = json.loads(result.stdout)
                version = version_info.get("terraform_version", "unknown")
            except json.JSONDecodeError:
                version = "unknown"
            console.print(f"[green]✓ Terraform installed (version {version})[/green]")
            return True
        else:
            console.print("[red]✗ Terraform not working properly[/red]")
            return False
    except FileNotFoundError:
        console.print("[red]✗ Terraform not installed[/red]")
        console.print("[dim]  Install from: https://developer.hashicorp.com/terraform/install[/dim]")
        return False
    except subprocess.TimeoutExpired:
        console.print("[red]✗ Terraform timed out[/red]")
        return False


def main() -> int:
    """Run all pre-flight checks."""
    console.print()
    console.print("[bold]Neo4j CDC Deployment - Pre-Flight Checks[/bold]")
    console.print("=" * 50)
    console.print()

    checks = [
        check_azure_cli,
        check_terraform_installed,
        check_python_dependencies,
        check_terraform_config,
    ]

    results = [check() for check in checks]
    all_passed = all(results)

    console.print()
    console.print("=" * 50)

    if all_passed:
        console.print("[bold green]✓ All pre-flight checks passed![/bold green]")
        console.print()
        console.print("[dim]Next steps:[/dim]")
        console.print("[dim]  cd terraform[/dim]")
        console.print("[dim]  terraform init[/dim]")
        console.print("[dim]  terraform apply[/dim]")
        return 0
    else:
        console.print("[bold red]✗ Some checks failed. Please resolve issues above.[/bold red]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
