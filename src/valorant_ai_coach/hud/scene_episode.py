"""Own observed native source episodes without granting lifecycle authorization.

A source initializer proposes image-supported reference identities. Assets cannot
supply previous PTS or pixels. Failed episodes cannot rejoin, and pending acquisition
retains metadata only. Every output remains descriptive until independent source,
world and UI qualification is provided by a separate production entrance.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any, Protocol

import numpy as np

from .scene_domains import (
    ImageU8,
    canonical_scene_image,
    domain_displacement_audit,
    joint_domain_audit,
)
from .scene_tracking import ReviewedWorldChain


class SceneReferenceAssets(Protocol):
    @property
    def references(self) -> list[dict[str, Any]]: ...

    @property
    def profile_sha256(self) -> str: ...


class SceneInitializer(Protocol):
    @property
    def references(self) -> SceneReferenceAssets: ...

    def recognize(self, current: ImageU8) -> dict[str, Any]: ...


class ObservedSceneEpisode:
    def __init__(
        self,
        initializer_factory: Callable[[], SceneInitializer],
        *,
        native_step_ticks: int,
        deferred_initialization: bool = False,
    ) -> None:
        if type(native_step_ticks) is not int or native_step_ticks <= 0:
            raise ValueError("positive native source frame spacing required")
        if type(deferred_initialization) is not bool:
            raise ValueError("explicit boolean deferred initialization required")
        self.bootstrap = initializer_factory()
        self.native_step_ticks = native_step_ticks
        self.chain: ReviewedWorldChain | None = None
        self.previous: tuple[int, str, str, ImageU8] | None = None
        self.terminated = False
        self.reference_id: str | None = None
        self.deferred_initialization = deferred_initialization
        self.pending_binding: tuple[int, str, str] | None = None

    def _stop(self, reason: str) -> dict[str, Any]:
        self.chain = None
        self.previous = None
        self.pending_binding = None
        self.terminated = True
        return self._result(reason)

    @staticmethod
    def _result(reason: str, **extra: Any) -> dict[str, Any]:
        return {
            "reason": reason,
            "descriptive_scene_link": False,
            "runtime_proof_authorized": False,
            "world_mask_authorized": False,
            "qualification_created": False,
            **extra,
        }

    def observe(
        self,
        native: Any,
        source_pts_ticks: int,
        *,
        source_epoch: str,
        discontinuity: bool = False,
    ) -> dict[str, Any]:
        if self.terminated:
            return self._result("episode_terminated")
        if (
            type(source_pts_ticks) is not int
            or not isinstance(source_epoch, str)
            or not source_epoch
            or type(discontinuity) is not bool
        ):
            return self._stop("invalid_source_binding")
        if discontinuity:
            return self._stop("explicit_discontinuity")
        # Validate the decoder boundary before touching shape/dtype or OpenCV.
        # A malformed frame must terminate an established episode rather than
        # raising AttributeError and leaving the previous observation alive.
        if not isinstance(native, np.ndarray):
            return self._stop("invalid_native_image")
        try:
            gray = canonical_scene_image(native)
        except ValueError:
            return self._stop("invalid_native_image")
        pixel_hash = hashlib.sha256(native.tobytes()).hexdigest()
        if self.pending_binding is not None:
            pending_pts, pending_epoch, pending_hash = self.pending_binding
            if (
                source_epoch != pending_epoch
                or source_pts_ticks - pending_pts != self.native_step_ticks
            ):
                return self._stop("source_epoch_or_native_gap")
            if pixel_hash == pending_hash:
                return self._stop("duplicate_native_pixels")
        if self.previous is None:
            proposal = self.bootstrap.recognize(gray)
            if not proposal["diagnostic_initialization_proposed"]:
                if self.deferred_initialization:
                    # Metadata only; no gray frame, world identities or prior
                    # scene history exists. A later seed starts at its own PTS.
                    self.pending_binding = (source_pts_ticks, source_epoch, pixel_hash)
                    return self._result("image_supported_initialization_pending")
                return self._stop("image_supported_initialization_unavailable")
            selected = next(
                p for p in proposal["proposals"] if p["diagnostic_initialization_proposed"]
            )
            reference = next(
                r
                for r in self.bootstrap.references.references
                if r["id"] == selected["reference_id"]
            )
            chain = ReviewedWorldChain(
                reference["image"],
                reference["boxes"],
                support_mode="adjacent_dense_world",
                dense_footprint="full_valid",
                seed_membership="symmetric_final",
            )
            # Retain only original reference identities; never extract new
            # current-frame features from a semantically unreviewed full crop.
            if not np.array_equal(gray, reference["image"]):
                binding = chain.advance(gray)
                if not binding["descriptive_supported"]:
                    return self._stop("observed_reference_identity_binding_failed")
            self.chain = chain
            self.reference_id = selected["reference_id"]
            self.previous = (source_pts_ticks, source_epoch, pixel_hash, gray.copy())
            self.pending_binding = None
            return self._result(
                "image_supported_observed_seed",
                source_pts_ticks=source_pts_ticks,
                source_pixel_sha256=pixel_hash,
                profile_sha256=proposal["profile_sha256"],
                reference_id=selected["reference_id"],
                reference_is_observed_previous_frame=False,
            )
        prior_pts, epoch, prior_hash, previous_gray = self.previous
        if epoch != source_epoch or source_pts_ticks - prior_pts != self.native_step_ticks:
            return self._stop("source_epoch_or_native_gap")
        if pixel_hash == prior_hash:
            return self._stop("duplicate_native_pixels")
        models: list[dict[str, Any]] = []
        assert self.chain is not None
        result = self.chain.advance(gray, dense_model_sink=models)
        if not result["descriptive_supported"] or not models:
            return self._stop(result["reason"])
        measurements: list[dict[str, Any]] = []
        domains = domain_displacement_audit(
            previous_gray,
            gray,
            self.chain.boxes,
            models[0]["model"],
            offset_sink=measurements,
        )
        joint = joint_domain_audit(self.chain.boxes, models[0]["model"], measurements)
        if not joint["locally_unique_joint_appearance"]:
            return self._stop("joint_scene_appearance_unavailable")
        # Preserve exactly the fixed-projection measurements used by the
        # joint gate. NCC is an appearance score, not a calibrated probability
        # of uninterrupted game time or an attested semantic world mask.
        witnesses = [
            {
                "region": region,
                "previous_box_640x360": list(self.chain.boxes[region]),
                "fixed_projection_ncc": domains[region]["predicted_ncc"],
            }
            for region in joint["fixed_projection_witness_regions"]
        ]
        self.previous = (source_pts_ticks, source_epoch, pixel_hash, gray.copy())
        return self._result(
            "descriptive_observed_scene_link",
            descriptive_scene_link=True,
            source_pts_ticks=source_pts_ticks,
            previous_source_pts_ticks=prior_pts,
            source_pixel_sha256=pixel_hash,
            previous_source_pixel_sha256=prior_hash,
            source_epoch=source_epoch,
            profile_sha256=self.bootstrap.references.profile_sha256,
            reference_id=self.reference_id,
            previous_to_current_affine_640x360=np.asarray(models[0]["model"]).tolist(),
            witnesses=witnesses,
            minimum_witness_ncc=min(p["fixed_projection_ncc"] for p in witnesses),
            score_semantics="minimum fixed-projection appearance NCC; not probability",
            joint=joint,
        )
