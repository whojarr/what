from __future__ import annotations

import random
import uuid

from civsim.models.entity import Entity
from civsim.models.world import (
    ClimateState,
    DEFAULT_ERA,
    GameState,
    MaterialDeposit,
    Region,
    RegionExit,
    Resources,
)


class WorldGenerator:
    def generate(self, seed: int, region_count: int = 2) -> GameState:
        rng = random.Random(seed)
        deposits = self._cave_deposits(rng)
        cave = Region(
            id="cave_chamber",
            name="The Cave",
            biome_tags=["cave", "sheltered", "damp", "spring"],
            energy_ceiling=0.5,
            water_availability=0.55,
            absent_materials=["wood", "plant_fiber", "clay"],
            always_available=["bone", "hide", "dung"],
            deposits=deposits,
            exits=[
                RegionExit(
                    id="passage_out",
                    name="Daylight passage",
                    target_region_id="outside_slope",
                    description="A narrow crack where pale daylight filters in, leading outward.",
                )
            ],
        )
        outside = Region(
            id="outside_slope",
            name="Outside the cave",
            biome_tags=["grassland", "exposed", "wind", "daylight"],
            energy_ceiling=0.85,
            water_availability=0.3,
            absent_materials=[
                "flint",
                "limestone",
                "iron_oxide",
                "sulfur",
                "manganese",
                "bone",
                "hide",
                "dung",
            ],
            always_available=["wood", "plant_fiber", "clay"],
            deposits=[],
            exits=[
                RegionExit(
                    id="passage_in",
                    name="Cave mouth",
                    target_region_id="cave_chamber",
                    description="The sheltered cave lies back through the passage.",
                    discovered=False,
                    accessible=False,
                )
            ],
        )
        fixtures = [
            Entity(
                id="natural_fire",
                name="Fire",
                type="component.fire",
                tags=["natural", "component", "fire", "machine"],
                capabilities={
                    "warmth_output": 0.35,
                    "light": 0.4,
                    "maintenance_complexity": 0.1,
                },
                region_id=cave.id,
                health=1.0,
                operational=True,
            ),
            Entity(
                id="natural_spring",
                name="Water",
                type="component.water",
                tags=["natural", "component", "water", "machine"],
                capabilities={
                    "water_output": 0.45,
                    "maintenance_complexity": 0.05,
                },
                region_id=cave.id,
                health=1.0,
                operational=True,
            ),
        ]
        regions = [cave, outside] if region_count >= 2 else [cave]
        return GameState(
            id=str(uuid.uuid4()),
            turn=0,
            rng_seed=seed,
            era=DEFAULT_ERA,
            path_divergence=0.0,
            invention_count=0,
            resources=Resources(
                warmth=0.12 + rng.random() * 0.06,
                water=0.38 + rng.random() * 0.08,
                food=0.06 + rng.random() * 0.06,
                materials=0.08 + rng.random() * 0.05,
                knowledge=0.03 + rng.random() * 0.04,
            ),
            climate=ClimateState(
                temperature_index=0.32 + rng.random() * 0.1,
                water_stress=0.15 + rng.random() * 0.1,
                atmospheric_instability=0.08 + rng.random() * 0.05,
                ecosystem_health=0.7 + rng.random() * 0.1,
            ),
            regions=regions,
            entities=fixtures,
            entity_names={
                "natural_fire": "Fire",
                "natural_spring": "Water",
            },
        )

    def _cave_deposits(self, rng: random.Random) -> list[MaterialDeposit]:
        iron_abundance = 0.35 + rng.random() * 0.25
        sulfur_present = rng.random() > 0.25
        manganese_present = rng.random() > 0.5
        deposits = [
            MaterialDeposit(
                id="deposit_flint",
                material_id="flint",
                abundance=0.75 + rng.random() * 0.2,
                depth="surface",
                discovered=True,
                description="Sharp flint stones scattered underfoot.",
            ),
            MaterialDeposit(
                id="deposit_limestone",
                material_id="limestone",
                abundance=0.85 + rng.random() * 0.1,
                depth="surface",
                discovered=True,
                description="Pale limestone forms the cave walls.",
            ),
            MaterialDeposit(
                id="deposit_iron_oxide",
                material_id="iron_oxide",
                abundance=iron_abundance,
                depth="surface",
                discovered=False,
                description="Dark red streaks run through the rock — iron ore.",
            ),
        ]
        if sulfur_present:
            deposits.append(
                MaterialDeposit(
                    id="deposit_sulfur",
                    material_id="sulfur",
                    abundance=0.25 + rng.random() * 0.35,
                    depth="deep",
                    discovered=False,
                    description="Yellow crystals glint in a deeper chamber.",
                )
            )
        if manganese_present:
            deposits.append(
                MaterialDeposit(
                    id="deposit_manganese",
                    material_id="manganese",
                    abundance=0.15 + rng.random() * 0.25,
                    depth="deep",
                    discovered=False,
                    description="Dark mineral veins run through deeper stone.",
                )
            )
        return deposits
