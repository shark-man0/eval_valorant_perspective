"""Diagnostic-profile compatibility entrance for the shared native episode.

The source reference loader stays diagnostic-only; output is never a qualified
continuity proof. Native ownership/tracking is shared with the production package.
"""
from valorant_ai_coach.hud.scene_episode import ObservedSceneEpisode
from valorant_ai_coach.hud.scene_references import WorldDomainBootstrap


class ObservedSceneChain(ObservedSceneEpisode):
    def __init__(self, profile_path, *, native_step_ticks, deferred_initialization=False):
        super().__init__(
            lambda: WorldDomainBootstrap(profile_path),
            native_step_ticks=native_step_ticks,
            deferred_initialization=deferred_initialization,
        )
