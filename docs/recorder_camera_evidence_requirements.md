# Recorder and current-camera evidence requirements

This is an offline DEVELOPMENT capture proposal, not an enabled collection
service or a Production ownership contract. Existing VOD identity remains UNKNOWN.

## What official services establish

Checked 2026-10-25: [VALORANT developer documentation](https://developer.riotgames.com/docs/valorant)
documents RSO account identification and content, match, ranked and status APIs.
RSO identifies the consenting authenticated account. It does not by itself bind
that account to the player currently displayed at a VOD frame. The documented
API list does not establish a current-camera endpoint. No authenticated request
or production-key access was performed, and no live camera payload was verified.
An API's existence or a match roster is not proof of VOD camera ownership.
League of Legends live-client APIs must not be assumed available in VALORANT.

The same documentation requires registration for player-facing products,
player opt-in for training/history data, and excludes immediate tactical live
overlays. Its personal-use-only API application restriction must be resolved
before proposing an API-backed product; local private research is not an API
approval. This work neither registers a product nor claims Riot approval.

[General policies](https://developer.riotgames.com/policies/general) require
supported ingestion services and prohibit de-anonymization of players not
reasonably identifiable from visible information. No hidden account lookup,
undocumented client endpoint, process-memory access or credential harvesting is
implemented. An approved integration's access to current-camera information
would require explicit verification of that field's meaning and permissions.

[Riot privacy notice](https://www.riotgames.com/en/privacy-notice) describes
Riot's practices, not this application's privacy permission. Our capture design
must separately obtain consent, minimize data, define retention/deletion and
restrict local access. Account IDs, aliases and frame-level identity stay private;
publication requires separate authorization. Tokens/credentials never belong in
source manifests, review packets, logs or Git.

## Proposed evidence bundle

Keep two independent records: consenting recorder identity and current camera
target. A future approved provider must supply both or leave the link UNKNOWN.
Each record needs evidence origin/provider/version, consent reference, a local
pseudonymous subject key, source SHA and physical-match binding. Current-camera
records additionally need native PTS/timebase, acquisition epoch, exact frame
or verified interval scope, liveness, phase, camera mode, target key and the
provider's explicit observation semantics. Unknown fields remain null.

Synchronize the recorder capture clock to native video PTS with measured error,
retain gaps and switches, and bind records to decoded-frame/encoded-frame
hashes. A static watermark, recording login, scoreboard identity, Agent match
or continuous image tracking cannot fill a missing camera-target record.
Do not propagate an exact-frame human confirmation to unsampled intervals.

Where no approved provider supplies the camera target, image-local human
review remains the available independent reference. Collect a small fixed set
of live, purchase, dead and spectated examples, with marker centers and phase
as separate questions. Human evidence is DEVELOPMENT GT only; it does not
automatically promote the recognizer or populate a Production Fact.

Before any ownership promotion, independently validate synchronization,
camera switches, missing metadata, alias collisions, spectator/death transitions
and observer mode on different episodes. Require recorder identity AND current
camera identity AND qualified view/geometry gates; absence of a spectator cue
is not a positive identity vote. This proposal does not claim that the necessary
provider exists or that current VODs contain the required unique identifiers.

Corrode/Bind reference build correspondence remains UNKNOWN. A separate verified
asset-build statement is still necessary; record date, current official diagrams
and successful outline alignment cannot supply it. The existing version gate
is unchanged.
