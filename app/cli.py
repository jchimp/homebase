import click

from .auth import get_admin_username, set_admin_credentials


@click.group()
def cli() -> None:
    """Hearth management commands."""


@cli.command("set-password")
@click.option("--username", default=None, help="Admin username (defaults to the current one)")
@click.password_option(prompt="New admin password")
def set_password(username: str | None, password: str) -> None:
    """Reset the admin credentials in the data store (data/auth.json)."""
    set_admin_credentials(username or get_admin_username(), password)
    click.echo("Password updated.")


if __name__ == "__main__":
    cli()
