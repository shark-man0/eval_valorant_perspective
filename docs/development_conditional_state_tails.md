# Conditional state tails (development only)

The shared `DevelopmentGameTimeline` offers two independent offline options:
`return_display_tail=True` and `buy_clock_tail=True`. A third option,
`current_hp_return_candidate=True`, requires `return_display_tail=True` and is
also disabled by default. They revise displayed state candidates after lifecycle inference;
neither changes the underlying observations, transition brackets, Round tokens,
Map gates, qualified Facts, or qualified Events.

`return_display_tail` targets a narrow victim-display continuation. The frame
must currently be `DEAD` only because of a competing victim-display hypothesis,
have unresolved camera mode and a weak current `SELF` view hypothesis, and have
no contrary current spectator, remote, death, downed, revival, or owner signal.
A directly observed next-Round `BUY` plus owner `SELF` return must occur within
the configured future window plus one display-quantization second, without a
Source/epoch break, contrary signal, or measured score conflict. With only
`return_display_tail=True`, the earlier Life and Camera values become `UNKNOWN`
with explicit alternatives, preserving the original behavior. The separate
`current_hp_return_candidate=True` option may select an unqualified `ALIVE`/`SELF`
candidate when the weak current `SELF` view includes a supported numeric HP
component. The `combat_report_visible` exclusion records that a visible report
prevents ownership qualification; it does not mean the report is absent. Other
eligible frames remain `UNKNOWN`. Both paths
retain `ALIVE`, `DEAD`, `DOWNED`, and `UNKNOWN` Life alternatives, plus competing
Camera alternatives. The later return does not establish the exact time or
prove that the earlier view was the recorder's.

`buy_clock_tail` targets a carried `BUY` inside a directly witnessed
`BUY`→`ACTIVE` bracket. A current numeric timer of 0 or 1 and a consistent,
measured score at all three points are required. The carried phase becomes
`UNKNOWN` with `BUY`, `ACTIVE`, and `UNKNOWN` alternatives. Clock expiry alone
does not establish the transition time.

In a fixed replay of eight development recordings, 17,693 one-second rows were
compared under identical native observations. The optional Round revision
changed five `BUY` rows to `UNKNOWN`. Of 117 victim-display `DEAD` second bins
revised by the return option, the separately enabled positive option changes
53 from `UNKNOWN` to unqualified `ALIVE`/`SELF` candidates
and 64 retained `UNKNOWN` Life. All 65 previously correct reviewed attributes
were retained; one exact human-confirmed frame gained correct Life and Camera
values. One other ALIVE control remains an abstention. Unlabelled candidate
changes are not measured recognition accuracy. Short, denser native observation
windows also recover positive Life/Camera states at some exact reviewed frames;
those are a different acquisition condition and must be compared separately.

`tests/unit/test_conditional_state_tails.py` covers positive cases, disabled
behavior, Source and epoch barriers, score conflicts, direct contradictory
signals, and time-window bounds. Production qualification remains unchanged.
