# 3D Asset Generation - CLI Usage Examples

Quick reference for using Gorgon's MODEL_BUILDER agent from the command line.

## Basic Usage

### Generate a Unity Script

```bash
# Simple terrain generator
gorgon run 3d-asset-build \
  --asset_request "Create a procedural terrain generator with Perlin noise" \
  --target_platform unity \
  --asset_type script

# Character controller
gorgon run game-character-setup \
  --character_name "Player" \
  --character_type player \
  --platform unity \
  --movement_style humanoid
```

### Generate a Blender Addon

```bash
gorgon run blender-addon \
  --addon_name "MeshTools" \
  --addon_description "Quick mesh editing utilities" \
  --features '["cleanup", "uv_unwrap", "batch_export"]' \
  --blender_version "4.0"
```

### Generate a Unity Shader

```bash
gorgon run unity-shader-pipeline \
  --shader_name "ToonWater" \
  --shader_type surface \
  --render_pipeline urp \
  --features '["transparency", "animated", "foam"]'
```

### Generate VFX/Particles

```bash
gorgon run vfx-particle-system \
  --effect_name "MagicExplosion" \
  --effect_type explosion \
  --platform unity \
  --style stylized \
  --color_palette '["#FF6B6B", "#FFE66D", "#4ECDC4"]'
```

### Generate Three.js Scene

```bash
gorgon run threejs-scene \
  --scene_name "ProductViewer" \
  --scene_type product-viewer \
  --interactions '["orbit-controls", "click-select"]' \
  --effects '["shadows", "reflections"]' \
  --framework react
```

## Platform-Specific Examples

### Unity Examples

```bash
# 2D Sprite Animation Controller
gorgon run 3d-asset-build \
  --asset_request "Create a 2D sprite animation system with blend trees" \
  --target_platform unity \
  --asset_type animation

# Inventory System
gorgon run 3d-asset-build \
  --asset_request "Create a grid-based inventory system with drag and drop" \
  --target_platform unity \
  --asset_type script

# Custom Editor Tool
gorgon run 3d-asset-build \
  --asset_request "Create an editor window for batch renaming GameObjects" \
  --target_platform unity \
  --asset_type script
```

### Blender Examples

```bash
# Procedural Modeling Addon
gorgon run blender-addon \
  --addon_name "ProceduralRocks" \
  --addon_description "Generate procedural rock meshes" \
  --features '["noise_displacement", "random_variations", "lod_generation"]'

# Batch Export Tool
gorgon run blender-addon \
  --addon_name "GameExporter" \
  --addon_description "Export objects with game-ready settings" \
  --features '["fbx_export", "texture_baking", "lod_export"]'
```

### Unreal Examples

```bash
# Blueprint Actor
gorgon run 3d-asset-build \
  --asset_request "Create an interactive door with timeline animation" \
  --target_platform unreal \
  --asset_type prefab

# Material Function
gorgon run 3d-asset-build \
  --asset_request "Create a triplanar mapping material function" \
  --target_platform unreal \
  --asset_type material
```

### Godot Examples

```bash
# Player Controller
gorgon run game-character-setup \
  --character_name "Player" \
  --character_type player \
  --platform godot \
  --movement_style humanoid

# Shader
gorgon run 3d-asset-build \
  --asset_request "Create a water shader with foam and waves" \
  --target_platform godot \
  --asset_type shader
```

## Output Handling

### Save to Files

```bash
# Save output to specific directory
gorgon run 3d-asset-build \
  --asset_request "Create a mesh generator" \
  --target_platform unity \
  --output-dir ./generated/unity/

# Generate with specific file names
gorgon run unity-shader-pipeline \
  --shader_name "CustomLit" \
  --output-dir ./Assets/Shaders/
```

### JSON Output

```bash
# Get structured JSON output
gorgon run 3d-asset-build \
  --asset_request "Create terrain system" \
  --target_platform unity \
  --format json > terrain_output.json
```

## Workflow Chaining

```bash
# Generate character, then create tests
gorgon run game-character-setup \
  --character_name "Enemy" \
  --platform unity \
  && gorgon run test-generator \
  --target "EnemyController.cs"
```

## Tips

1. **Use quotes for complex requests**: Wrap multi-line requests in quotes
2. **JSON for arrays**: Use JSON format for array parameters like features
3. **Check available workflows**: Run `gorgon list` to see all workflows
4. **Dry run**: Add `--dry-run` to preview without execution
5. **Verbose output**: Add `-v` or `--verbose` for detailed logs
