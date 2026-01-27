#!/usr/bin/env python3
"""Example: Generate a procedural terrain system for Unity.

This example demonstrates using the MODEL_BUILDER agent to create
a complete procedural terrain generation system.

Usage:
    python examples/3d-assets/unity_terrain_example.py
"""

import asyncio
from pathlib import Path

# Add src to path for imports
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from test_ai.workflow import WorkflowExecutor, WorkflowLoader


async def generate_unity_terrain():
    """Generate a procedural terrain system for Unity."""

    # Load the 3D asset build workflow
    loader = WorkflowLoader()
    workflow = loader.load("3d-asset-build")

    # Configure inputs for terrain generation
    inputs = {
        "asset_request": """
        Create a procedural terrain generation system with:
        - Perlin noise-based heightmap generation
        - Multiple octaves for detail (fBm)
        - Real-time terrain modification in editor
        - LOD system with 4 levels
        - Texture splatting based on height and slope
        - Water plane with simple waves
        """,
        "target_platform": "unity",
        "asset_type": "script",
        "specifications": {
            "max_polygons": 100000,
            "texture_resolution": "2048",
            "lod_levels": 4,
        },
    }

    # Execute the workflow
    executor = WorkflowExecutor()
    result = await executor.execute(workflow, inputs)

    if result.success:
        print("✓ Terrain system generated successfully!")
        print("\nGenerated assets:")
        for asset in result.outputs.get("assets", []):
            print(f"  - {asset['name']} ({asset['type']})")

        print("\nInstructions:")
        for instruction in result.outputs.get("instructions", []):
            print(f"  {instruction['step']}. {instruction['action']}")
    else:
        print(f"✗ Generation failed: {result.error}")

    return result


async def generate_blender_addon():
    """Generate a Blender addon for quick mesh operations."""

    loader = WorkflowLoader()
    workflow = loader.load("blender-addon")

    inputs = {
        "addon_name": "QuickMeshTools",
        "addon_description": "Quick mesh editing utilities for common operations",
        "features": [
            "One-click mesh cleanup (remove doubles, fix normals)",
            "Quick UV unwrap presets",
            "Batch rename selected objects",
            "Export selected to FBX with game-ready settings",
        ],
        "blender_version": "4.0",
    }

    executor = WorkflowExecutor()
    result = await executor.execute(workflow, inputs)

    if result.success:
        print("✓ Blender addon generated!")
        # The addon code would be in result.outputs["addon_code"]

    return result


async def generate_character_controller():
    """Generate a complete character controller for Unity."""

    loader = WorkflowLoader()
    workflow = loader.load("game-character-setup")

    inputs = {
        "character_name": "PlayerCharacter",
        "character_type": "player",
        "platform": "unity",
        "movement_style": "humanoid",
        "features": ["combat", "inventory"],
        "animation_states": [
            "idle",
            "walk",
            "run",
            "sprint",
            "jump",
            "fall",
            "land",
            "attack_light",
            "attack_heavy",
            "dodge",
            "block",
            "death",
        ],
    }

    executor = WorkflowExecutor()
    result = await executor.execute(workflow, inputs)

    if result.success:
        print("✓ Character controller generated!")
        print("\nFiles created:")
        print(f"  - {inputs['character_name']}Controller.cs")
        print(f"  - {inputs['character_name']}Animator.controller")

    return result


async def generate_threejs_product_viewer():
    """Generate a Three.js product viewer for web."""

    loader = WorkflowLoader()
    workflow = loader.load("threejs-scene")

    inputs = {
        "scene_name": "ProductViewer",
        "scene_type": "product-viewer",
        "models": ["product.glb"],
        "interactions": ["orbit-controls", "click-select", "hover"],
        "effects": ["shadows", "reflections", "post-processing"],
        "responsive": True,
        "framework": "vanilla",
    }

    executor = WorkflowExecutor()
    result = await executor.execute(workflow, inputs)

    if result.success:
        print("✓ Three.js product viewer generated!")

    return result


if __name__ == "__main__":
    print("=" * 60)
    print("Gorgon 3D Asset Generation Examples")
    print("=" * 60)

    # Run the terrain example
    print("\n[1/4] Generating Unity Terrain System...")
    asyncio.run(generate_unity_terrain())

    print("\n[2/4] Generating Blender Addon...")
    asyncio.run(generate_blender_addon())

    print("\n[3/4] Generating Character Controller...")
    asyncio.run(generate_character_controller())

    print("\n[4/4] Generating Three.js Product Viewer...")
    asyncio.run(generate_threejs_product_viewer())

    print("\n" + "=" * 60)
    print("All examples complete!")
