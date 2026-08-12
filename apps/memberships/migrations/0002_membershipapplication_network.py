import django.db.models.deletion
from django.db import migrations, models


def backfill_network(apps, schema_editor):
    """Every MembershipApplication row created before this migration was
    implicitly "against the primary network" (there was only ever one
    Network row and apps.networks.services.get_primary_network() always
    resolved to it) — so point them at the oldest Network row explicitly,
    matching that prior behaviour exactly rather than guessing.
    """
    Network = apps.get_model("networks", "Network")
    MembershipApplication = apps.get_model("memberships", "MembershipApplication")
    primary_network = Network.objects.order_by("created_at").first()
    if primary_network is not None:
        MembershipApplication.objects.filter(network__isnull=True).update(network=primary_network)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("networks", "0001_initial"),
        ("memberships", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="membershipapplication",
            name="network",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="membership_applications",
                to="networks.network",
            ),
        ),
        migrations.RunPython(backfill_network, noop_reverse),
        migrations.AlterField(
            model_name="membershipapplication",
            name="network",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="membership_applications",
                to="networks.network",
            ),
        ),
        migrations.AddIndex(
            model_name="membershipapplication",
            index=models.Index(fields=["network", "status"], name="memberships_network_c78d99_idx"),
        ),
    ]
