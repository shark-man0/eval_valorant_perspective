# Event actor contract

An event's `actor` identifies its semantic subject. It does not identify the
module that produced the event. Producer provenance remains the responsibility
of `config/event_source_contract_v1.json`'s `primary_producer` field.

Round lifecycle events use `actor: "system"`: `round_start` and `round_end`
describe match-rule lifecycle transitions, rather than an action attributable
to a particular team or player. `team` is reserved for an event that describes
a collective team's action; `player` is for an action attributable to the
player. HUD may observe a lifecycle event, but that does not make HUD the event
actor.

The producer contract supports optional `allowed_actors` metadata per event
type. The current contract declares `system` for `round_start` and `round_end`.
Runtime actor validation is intentionally limited to these lifecycle types so
this additive metadata does not change existing semantics for other events.
Contracts predating `allowed_actors` remain valid and retain producer-only
validation.

The event schema already carries actor and attributes. Source/evidence detail
that needs to travel with an event belongs in explicit event attributes; actor
must not be overloaded with producer or evidence provenance. Package and trace
layers should preserve actor verbatim rather than translating it to satisfy a
consumer.
