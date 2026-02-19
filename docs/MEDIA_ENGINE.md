# GORGON MEDIA ENGINE — Autonomous AI Content Empire

## Master Architecture Document

*One AI. Three channels. Eight languages. Zero human bottleneck.*

---

## Table of Contents

1. [Vision & Scope](#vision--scope)
2. [System Architecture](#system-architecture)
3. [Channel Configurations](#channel-configurations)
4. [Voice System — Epic Narration Profiles](#voice-system--epic-narration-profiles)
5. [Multi-Language Engine](#multi-language-engine)
6. [Visual Generation System](#visual-generation-system)
7. [Thumbnail Strategy & Generation](#thumbnail-strategy--generation)
8. [Animus — The Creative Brain](#animus--the-creative-brain)
9. [Gorgon Agent Specifications](#gorgon-agent-specifications)
10. [Autonomous Distribution System](#autonomous-distribution-system)
11. [Content Strategy & Scheduling](#content-strategy--scheduling)
12. [Analytics & Feedback Loop](#analytics--feedback-loop)
13. [Infrastructure & Cost](#infrastructure--cost)
14. [Build Order & Timeline](#build-order--timeline)

---

## Vision & Scope

### What We're Building

A fully autonomous AI content generation and distribution system that:

- Operates **3 content channels** with distinct identities and audiences
- Produces content in **8 languages** per channel
- Generates **every element**: scripts, narration, visuals, thumbnails, captions, metadata
- Distributes to YouTube automatically with optimized scheduling
- Learns from performance data and adjusts content strategy
- Runs 24/7 with minimal human oversight
- Is orchestrated by **Gorgon** and creatively directed by **Animus** (Ollama)

### The Channels

| Channel | Content | Audience | Languages | Daily Output |
|---------|---------|----------|-----------|-------------|
| **Story Fire** | World folklore & mythology (Storyteller style) | General / all ages | 8 | 1 Short × 8 langs = 8 videos |
| **New Eden Whispers** | EVE Online Chronicles & lore | Gamers / sci-fi fans | 4 | 1 Short × 4 langs = 4 videos |
| **Holmes Wisdom** | Science of Mind / Ernest Holmes | Spiritual seekers | 4 | 1 Short × 4 langs = 4 videos |

**Daily total: 16 videos across 3 channels and 8 languages.**
**Monthly total: ~480 videos.**
**Annual total: ~5,760 videos.**

### The Autonomous Loop

```
┌─────────────────────────────────────────────────────────┐
│                                                          │
│   ┌──────────┐     ┌──────────┐     ┌──────────┐       │
│   │  ANIMUS   │────▶│  GORGON  │────▶│ YOUTUBE  │       │
│   │ (Creative │     │ (Produce │     │ (Publish │       │
│   │  Brain)   │     │  & Build)│     │  & Grow) │       │
│   └──────────┘     └──────────┘     └────┬─────┘       │
│        ▲                                  │              │
│        │         ┌──────────┐             │              │
│        └─────────│ ANALYTICS│◀────────────┘              │
│                  │ (Learn & │                             │
│                  │  Adapt)  │                             │
│                  └──────────┘                             │
│                                                          │
│              FULLY AUTONOMOUS LOOP                        │
└─────────────────────────────────────────────────────────┘
```

---

## System Architecture

### High-Level Architecture

```
╔══════════════════════════════════════════════════════════════╗
║                    GORGON ORCHESTRATOR                       ║
║                   (Agent Lifecycle Manager)                   ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  ┌─────────────── CREATIVE LAYER ─────────────────────┐     ║
║  │                                                     │     ║
║  │  ANIMUS (Ollama LLM)                               │     ║
║  │  ├── Script Generation (per channel voice)          │     ║
║  │  ├── Translation Direction (per language)            │     ║
║  │  ├── Thumbnail Concept (per culture/theme)          │     ║
║  │  ├── Content Strategy (analytics-informed)          │     ║
║  │  └── Quality Review (self-evaluation)               │     ║
║  │                                                     │     ║
║  └─────────────────────────────────────────────────────┘     ║
║                                                              ║
║  ┌─────────────── PRODUCTION LAYER ───────────────────┐     ║
║  │                                                     │     ║
║  │  BARD ──── Script extraction & adaptation           │     ║
║  │  BABEL ─── Multi-language translation & adaptation  │     ║
║  │  VOICE ─── Epic TTS narration (per lang, per char)  │     ║
║  │  PAINTER ─ Visual generation (SD + style system)    │     ║
║  │  THUMB ─── Thumbnail generation & optimization      │     ║
║  │  SCRIBE ── Caption generation (per language)        │     ║
║  │  WEAVER ── Final video assembly (per language)      │     ║
║  │                                                     │     ║
║  └─────────────────────────────────────────────────────┘     ║
║                                                              ║
║  ┌─────────────── DISTRIBUTION LAYER ─────────────────┐     ║
║  │                                                     │     ║
║  │  HERALD ── YouTube upload, metadata, scheduling     │     ║
║  │  KEEPER ── Content calendar & tale selection         │     ║
║  │  ORACLE ── Analytics collection & interpretation    │     ║
║  │  MIRROR ── Cross-platform distribution (future)     │     ║
║  │                                                     │     ║
║  └─────────────────────────────────────────────────────┘     ║
║                                                              ║
║  ┌─────────────── SHARED STATE ───────────────────────┐     ║
║  │                                                     │     ║
║  │  Channel configs │ Language profiles │ Voice models  │     ║
║  │  Tale database   │ Performance data  │ Schedule      │     ║
║  │  Asset library   │ Upload queue      │ Health status │     ║
║  │                                                     │     ║
║  └─────────────────────────────────────────────────────┘     ║
╚══════════════════════════════════════════════════════════════╝
```

### Data Flow Per Video

```
1. KEEPER selects tale + culture + language schedule
       │
2. BARD (via ANIMUS) extracts dramatic scene, writes script
       │
3. BABEL (via ANIMUS) translates/adapts script into target languages
       │
4. VOICE generates narration audio per language (epic voice profiles)
       │
5. PAINTER generates 4-6 scene illustrations (culture-specific style)
       │
6. THUMB generates thumbnail (optimized for CTR)
       │
7. SCRIBE generates captions per language via Whisper
       │
8. WEAVER assembles final MP4 per language (same visuals, different audio/captions)
       │
9. HERALD uploads to YouTube with localized metadata per language
       │
10. ORACLE tracks performance, feeds back to KEEPER/ANIMUS
```

**Key efficiency:** Steps 5-6 (visuals + thumbnail) are done ONCE per tale. Only audio, captions, and metadata change per language. A single tale produces 4-8 videos from one visual generation pass.

---

## Channel Configurations

### Story Fire

```yaml
channel:
  name: "Story Fire"
  tagline: "Tales told the old way."
  identity: "The Storyteller and The Dog — warm, conspiratorial, darkly whimsical"
  audience: "General / all ages (NOT 'Made for Kids')"
  
  content:
    source: "Public domain world folklore, fairy tales, mythology"
    format: "40-55 second YouTube Shorts"
    daily_output: 1 tale × 8 languages = 8 videos
    narrator: "The Storyteller (warm, aged, conspiratorial)"
    companion: "The Dog (skeptical, blunt, endearing)"
    
  languages:
    - {code: "en", name: "English", channel_suffix: "", primary: true}
    - {code: "es", name: "Spanish", channel_suffix: "Español"}
    - {code: "fr", name: "French", channel_suffix: "Français"}
    - {code: "pt", name: "Portuguese", channel_suffix: "Português"}
    - {code: "de", name: "German", channel_suffix: "Deutsch"}
    - {code: "ja", name: "Japanese", channel_suffix: "日本語"}
    - {code: "hi", name: "Hindi", channel_suffix: "हिन्दी"}
    - {code: "ar", name: "Arabic", channel_suffix: "العربية"}
    
  visual_style: "Painterly, illuminated manuscript, firelit warmth"
  thumbnail_style: "Warm amber border, serif title, tale illustration"
```

### New Eden Whispers

```yaml
channel:
  name: "New Eden Whispers"
  tagline: "The untold stories of New Eden."
  identity: "Epic sci-fi narrator — gravitas, weight, cosmic scale"
  audience: "Gamers, sci-fi fans, EVE players"
  
  content:
    source: "EVE Online Chronicles (CCP content, used under content creation terms)"
    format: "40-55 second YouTube Shorts"
    daily_output: 1 chronicle × 4 languages = 4 videos
    narrator: "The Chronicler (deep, authoritative, epic)"
    companion: null  # Solo narrator
    
  languages:
    - {code: "en", name: "English", primary: true}
    - {code: "es", name: "Spanish"}
    - {code: "de", name: "German"}
    - {code: "ru", name: "Russian"}  # Large EVE playerbase
    
  visual_style: "Cinematic sci-fi, faction-specific color grading"
  thumbnail_style: "Dark space background, bold sans-serif title, faction colors"
```

### Holmes Wisdom

```yaml
channel:
  name: "Holmes Wisdom"
  tagline: "Century-old wisdom. Modern clarity."
  identity: "Warm, authoritative teacher — mentor tone, not preacher"
  audience: "Spiritual seekers, self-improvement, meditation practitioners"
  
  content:
    source: "Ernest Holmes public domain works (pre-1929)"
    format: "30-45 second YouTube Shorts"
    daily_output: 1 passage × 4 languages = 4 videos
    narrator: "The Guide (warm, measured, quietly powerful)"
    companion: null  # Solo narrator
    
  languages:
    - {code: "en", name: "English", primary: true}
    - {code: "es", name: "Spanish"}
    - {code: "pt", name: "Portuguese"}
    - {code: "fr", name: "French"}
    
  visual_style: "Ethereal, cosmic, contemplative gradients"
  thumbnail_style: "Soft gradient background, clean sans-serif quote text"
```

---

## Voice System — Epic Narration Profiles

### Philosophy

Every channel needs a voice that is **instantly recognizable** and **emotionally compelling**. These are not generic TTS readouts — they are *performances*. The voice IS the brand.

### Voice Profiles

#### Story Fire — The Storyteller

```yaml
storyteller:
  character: "An ancient keeper of tales, warm and conspiratorial"
  reference_performances:
    - "John Hurt in Jim Henson's The Storyteller"
    - "Ian McKellen's fireside warmth"
    - "Patrick Stewart's measured authority with a twinkle"
  
  tts_config:
    engine: "elevenlabs"
    voice_id: "custom_clone_or_adam"
    settings:
      stability: 0.35           # LOW — maximum expressiveness
      similarity_boost: 0.75
      style: 0.65               # High dramatic range
      use_speaker_boost: true
    speed: 0.85                  # Slower than normal — fireside pace
    
  vocal_direction:
    - "Speak as if confiding a secret to a trusted friend"
    - "Lean into whispers for dark moments"
    - "Build momentum with rolling, rhythmic sentences"
    - "Occasional surprised delight: 'And THEN — oh, this is the part...'"
    - "Never rush. Pauses are part of the music."
    
  per_language_adaptation:
    es: {speed: 0.90, style: 0.70}   # Spanish is naturally more expressive
    fr: {speed: 0.85, style: 0.60}   # French — elegant restraint
    de: {speed: 0.80, style: 0.55}   # German — measured, dark fairy tale tone
    ja: {speed: 0.80, style: 0.50}   # Japanese — restrained, atmospheric
    pt: {speed: 0.90, style: 0.70}   # Portuguese — warm, rhythmic
    hi: {speed: 0.85, style: 0.65}   # Hindi — expressive, storytelling tradition
    ar: {speed: 0.80, style: 0.60}   # Arabic — poetic, flowing
```

#### Story Fire — The Dog

```yaml
dog:
  character: "Skeptical, loyal, slightly anxious companion"
  reference_performances:
    - "Brian Henson's Dog from The Storyteller"
    - "Martin Freeman's everymanness"
    - "Simon Pegg's dry wit"
  
  tts_config:
    engine: "elevenlabs"
    voice_id: "custom_clone_or_charlie"
    settings:
      stability: 0.50           # More stable — blunt delivery
      similarity_boost: 0.80
      style: 0.35               # Conversational, not dramatic
      use_speaker_boost: true
    speed: 1.0                   # Normal pace — contrast with Storyteller
    
  vocal_direction:
    - "Short, punchy sentences"
    - "Skeptical but lovable"
    - "Slightly modern cadence — grounds the Storyteller's lyricism"
    - "Occasional genuine fear or delight breaks through the skepticism"
```

#### New Eden Whispers — The Chronicler

```yaml
chronicler:
  character: "A voice from the void — epic, weighty, cosmic narrator"
  reference_performances:
    - "Cate Blanchett's Galadriel opening narration (LOTR)"
    - "Keith David's documentary narration"
    - "Mass Effect's Codex narrator"
  
  tts_config:
    engine: "elevenlabs"
    voice_id: "custom_clone_or_onyx"
    settings:
      stability: 0.30           # Very expressive for epic moments
      similarity_boost: 0.80
      style: 0.75               # Maximum dramatic range
      use_speaker_boost: true
    speed: 0.80                  # Slow, deliberate — every word has weight
    
  vocal_direction:
    - "Speak as if narrating the history of civilizations"
    - "Weight on key words — 'empire', 'betrayal', 'immortal'"
    - "Long pauses before revelations"
    - "Quiet menace for dark content, not shouting"
    
  per_language_adaptation:
    es: {speed: 0.85, style: 0.70}
    de: {speed: 0.80, style: 0.70}   # German — perfect for epic narration
    ru: {speed: 0.80, style: 0.80}   # Russian — dramatic tradition
```

#### Holmes Wisdom — The Guide

```yaml
guide:
  character: "A warm, grounded teacher — quiet power, not preaching"
  reference_performances:
    - "Morgan Freeman's calm authority"
    - "Alan Watts' playful wisdom"
    - "Thich Nhat Hanh's gentle directness"
  
  tts_config:
    engine: "elevenlabs"
    voice_id: "custom_clone_or_adam"
    settings:
      stability: 0.45           # Balanced — warm but clear
      similarity_boost: 0.80
      style: 0.45               # Moderate expressiveness
      use_speaker_boost: true
    speed: 0.82                  # Measured, contemplative
    
  vocal_direction:
    - "Speak as if helping someone see what they already know"
    - "No urgency — quiet confidence"
    - "Pauses for reflection, not drama"
    - "Warmth, not distance"
```

### Voice Generation Infrastructure

```python
"""
Voice generation system supporting multiple characters,
languages, and emotional ranges.

Architecture:
  1. Generate audio in source language (English)
  2. For other languages:
     a. BABEL translates script
     b. VOICE generates with language-specific voice model
     c. VOICE adjusts timing/pacing per language norms

ElevenLabs supports 29 languages natively with voice consistency.
For languages not in ElevenLabs: use Coqui XTTS (local, free).
"""

class VoiceEngine:
    # ElevenLabs supported languages (subset — our targets)
    ELEVENLABS_LANGUAGES = {
        "en", "es", "fr", "de", "pt", "hi", "ar", "ja", 
        "ru", "zh", "ko", "it", "pl", "nl", "tr"
    }
    
    # Fallback engine for unsupported languages
    FALLBACK_ENGINE = "coqui_xtts"
    
    def generate_narration(
        self,
        script: dict,
        language: str,
        voice_profile: dict,
        channel: str,
    ) -> AudioFile:
        """Generate narration for a specific language."""
        
        # Get language-specific voice adjustments
        lang_config = voice_profile.get("per_language_adaptation", {})
        config = {**voice_profile["tts_config"]["settings"]}
        if language in lang_config:
            config.update(lang_config[language])
        
        # Select engine
        if language in self.ELEVENLABS_LANGUAGES:
            engine = "elevenlabs"
        else:
            engine = self.FALLBACK_ENGINE
        
        # Build audio sequence
        segments = self._build_sequence(script, voice_profile, language)
        
        # Generate each segment
        audio_parts = []
        for seg in segments:
            if seg["type"] == "speech":
                audio = self._generate_speech(
                    text=seg["text"],
                    voice_id=seg["voice_id"],
                    config=config,
                    engine=engine,
                    language=language,
                )
                audio_parts.append(audio)
            elif seg["type"] == "pause":
                audio_parts.append(Silence(duration=seg["duration"]))
            elif seg["type"] == "ambient":
                audio_parts.append(AmbientLoop(
                    source=seg["source"],
                    duration=seg["duration"],
                    volume=seg["volume"],
                ))
        
        # Mix: narration over ambient
        narration = concatenate(audio_parts)
        ambient = self._get_ambient(voice_profile, duration=narration.duration)
        
        return mix_audio(narration, ambient, ambient_volume=0.08)
```

---

## Multi-Language Engine

### The BABEL Agent

BABEL doesn't just translate — it **culturally adapts**. A Japanese narration of a Norse folk tale needs different rhythms than a Spanish one. The Storyteller's voice should feel native in every language.

```python
"""
BABEL Agent — Multi-language script adaptation.

NOT just translation. Cultural adaptation:
  - Rhythm and cadence shift per language
  - Idiomatic expressions replace literal translations
  - Oral tradition markers adapt (repetitions, call-response)
  - The Dog's personality adapts to cultural humor norms
  - Storyteller's warmth translates without losing character
"""

class BabelAgent:
    
    SYSTEM_PROMPT = """You are a master translator specializing in oral 
storytelling traditions across cultures. You don't just translate words — 
you adapt the FEEL of the narration for native speakers of the target 
language.

RULES:
1. Maintain the Storyteller's warm, conspiratorial tone in the target language
2. Adapt oral tradition markers — repetitions, rhythms, direct address
3. Use natural idioms, not literal translations
4. The Dog's voice should feel colloquial and natural in the target language
5. Cultural references that don't translate should be adapted, not explained
6. Maintain the [pause], [whisper], [louder] vocal cues
7. Keep word count within 10% of the original (crucial for video timing)
8. The translated script must SOUND like it was originally written in 
   the target language

Output the translated script in the same JSON format as the input.
Add a field "translation_notes" with any cultural adaptations made."""

    LANGUAGE_DIRECTIONS = {
        "es": "Spanish narration should lean into the musical, flowing quality. "
              "The Storyteller can be slightly more openly emotional. "
              "The Dog can use gentle humor common in Latin storytelling.",
              
        "fr": "French narration should have elegant restraint with sudden "
              "bursts of expressiveness. The Storyteller has a philosophical "
              "edge. The Dog is dryly sardonic.",
              
        "de": "German narration should be measured and atmospheric. Perfect "
              "for dark fairy tales — lean into the Gothic tradition. "
              "The Dog is pragmatic and direct.",
              
        "pt": "Portuguese narration should be warm and rhythmic, especially "
              "Brazilian Portuguese. The Storyteller is a warm uncle figure. "
              "The Dog is charmingly anxious.",
              
        "ja": "Japanese narration should respect the storytelling tradition "
              "of rakugo — measured, atmospheric, with implied emotion. "
              "The Dog is politely skeptical. Use appropriate honorifics.",
              
        "hi": "Hindi narration should tap into the rich oral tradition of "
              "kathavachak (storytellers). Warm, expressive, with natural "
              "code-switching between formal and colloquial. The Dog is loyal "
              "but comically worried.",
              
        "ar": "Arabic narration should channel the hakawati tradition — "
              "poetic, flowing, with a natural musicality. The Storyteller "
              "is a wise elder. The Dog is an earnest fool.",
              
        "ru": "Russian narration should be rich and dramatic — Russian has "
              "a deep fairy tale tradition (skazka). The Storyteller is a "
              "babushka/dedushka figure. The Dog is world-weary.",
    }

    async def translate_script(
        self,
        script: dict,
        target_language: str,
        channel: str,
    ) -> dict:
        """Translate and culturally adapt a script."""
        
        lang_direction = self.LANGUAGE_DIRECTIONS.get(target_language, "")
        
        prompt = f"""Translate and culturally adapt this {channel} script 
into {target_language}.

Language-specific direction: {lang_direction}

Source script:
{json.dumps(script, indent=2)}

Maintain JSON format. Keep vocal cues. Target similar word count.
Output translated JSON only."""

        response = await self.animus.generate(
            prompt=prompt,
            system=self.SYSTEM_PROMPT,
            temperature=0.6,  # Lower temp for translation accuracy
        )
        
        return json.loads(response)
```

### Language Distribution Strategy

Not all languages get the same channels:

```
Story Fire (8 languages — broadest appeal):
  EN → Main channel
  ES → Story Fire Español (or multi-lang main channel)
  FR → Story Fire Français
  PT → Story Fire Português
  DE → Story Fire Deutsch
  JA → Story Fire 日本語
  HI → Story Fire हिन्दी
  AR → Story Fire العربية

New Eden Whispers (4 languages — EVE playerbase):
  EN → Main channel
  ES → Secondary
  DE → Secondary (large EU EVE community)
  RU → Secondary (large RU EVE community)

Holmes Wisdom (4 languages — spiritual seekers):
  EN → Main channel
  ES → Secondary (huge Spanish spiritual market)
  PT → Secondary (huge Brazilian spiritual market)
  FR → Secondary
```

### Channel Architecture for Multi-Language

Two approaches:

**Option A: Separate channels per language**
- story-fire-en, story-fire-es, story-fire-fr...
- Pro: Clean analytics per language, native audience feels ownership
- Con: 24 channels to manage, fragmented subscribers

**Option B: Single channel, multi-language uploads with localized metadata**
- One "Story Fire" channel, videos tagged and titled per language
- Pro: Consolidated subscriber count, simpler management
- Con: Algorithm confusion, mixed-language feed

**Option C (Recommended): Hub + Spoke**
- Main English channel = primary brand
- 2-3 highest-performing language channels spun off later
- Start with multi-language on ONE channel, split when a language hits critical mass (1K+ subs in that language)

```yaml
language_strategy:
  phase_1:  # Month 1-3
    approach: "All languages on main channel"
    reason: "Test which languages perform, build total view count"
    
  phase_2:  # Month 3-6
    approach: "Split top 2 performing non-English languages into own channels"
    trigger: "When a language consistently gets 30%+ of views"
    
  phase_3:  # Month 6+
    approach: "Full spoke channels for top performers"
    trigger: "When any language channel independently qualifies for YPP"
```

---

## Visual Generation System

### PAINTER Agent — Scene Illustrations

Each tale generates **4-6 scene illustrations** used across ALL language versions. This is the most compute-intensive step but only runs once per tale.

```python
class PainterAgent:
    """Generate scene illustrations matching tale culture and mood."""
    
    # Resolution for YouTube Shorts (9:16)
    WIDTH = 1080
    HEIGHT = 1920
    
    # SD model selection
    MODELS = {
        "painterly": "stable-diffusion-xl-base-1.0",
        "anime": "anything-v5",       # For Japanese tales
        "realistic": "realistic-vision-v5",
    }
    
    async def generate_tale_visuals(
        self,
        script: dict,
        channel_config: dict,
    ) -> list[Path]:
        """Generate all visuals for a tale (shared across languages)."""
        
        culture = script.get("culture", "european")
        visual_cues = script.get("visual_cues", [])
        mood = script.get("mood", "warm_dark")
        palette = CULTURE_PALETTES[culture]
        
        images = []
        
        # Scene 1: Hook image (the attention-grabber)
        hook_img = await self._generate(
            scene=visual_cues[0] if visual_cues else script["hook"],
            culture=culture,
            mood=mood,
            style=palette["sd_style"],
            emphasis="dramatic, attention-grabbing composition",
        )
        images.append(hook_img)
        
        # Scenes 2-4: Story progression
        for i, cue in enumerate(visual_cues[1:4]):
            img = await self._generate(
                scene=cue,
                culture=culture,
                mood=mood,
                style=palette["sd_style"],
                emphasis="narrative progression, visual storytelling",
            )
            images.append(img)
        
        # Scene 5: Closing image (emotional resolution)
        closing_img = await self._generate(
            scene=script.get("closing", visual_cues[-1] if visual_cues else ""),
            culture=culture,
            mood=mood,
            style=palette["sd_style"],
            emphasis="emotional resolution, lingering beauty",
        )
        images.append(closing_img)
        
        return images
    
    async def _generate(
        self,
        scene: str,
        culture: str,
        mood: str,
        style: str,
        emphasis: str,
    ) -> Path:
        """Generate a single scene image."""
        
        # ANIMUS writes the actual SD prompt (better than templates)
        sd_prompt = await self.animus.generate(
            prompt=f"""Write a Stable Diffusion prompt for this scene:
Scene: {scene}
Culture: {culture}
Mood: {mood}
Art style: {style}
Emphasis: {emphasis}

Write ONLY the prompt. No explanation. Include negative prompt.
Format: PROMPT: [prompt] | NEGATIVE: [negative]""",
            temperature=0.7,
        )
        
        prompt, negative = self._parse_prompt(sd_prompt)
        
        image = await self.sd_pipeline(
            prompt=prompt,
            negative_prompt=negative,
            width=self.WIDTH,
            height=self.HEIGHT,
            num_inference_steps=25,
            guidance_scale=7.5,
        )
        
        # Apply culture-specific post-processing
        image = self._apply_post_processing(image, culture, mood)
        
        return self._save(image)
```

---

## Thumbnail Strategy & Generation

### Why Thumbnails Matter

Thumbnails are the **single biggest factor in click-through rate (CTR)**. A video that would get 100K views with a great thumbnail gets 10K with a bad one. For Shorts specifically, thumbnails appear in the Shorts shelf, subscription feed, and search results.

### Thumbnail Design Philosophy

**Per Channel:**

| Channel | Style | Key Elements |
|---------|-------|-------------|
| **Story Fire** | Warm, painterly, inviting | Amber border, tale illustration, serif title, firelight glow |
| **New Eden Whispers** | Dark, cinematic, epic | Space backdrop, faction color accent, bold sans-serif, glow effects |
| **Holmes Wisdom** | Clean, ethereal, peaceful | Soft gradient, minimal text, centered quote fragment, light rays |

### The THUMB Agent

```python
"""
THUMB Agent — Automated thumbnail generation.

Strategy:
  1. ANIMUS generates thumbnail concept based on tale content
  2. PAINTER generates base illustration (or reuses best scene image)
  3. THUMB composites text, borders, branding, and effects
  4. THUMB generates 3 variants (A/B testing potential)
  
Design principles:
  - HIGH CONTRAST: Must be readable at 120x90px (mobile feed)
  - EMOTIONAL FACE OR DRAMATIC SCENE: These get highest CTR
  - 3-5 WORDS MAX: Large, bold, readable
  - CONSISTENT BRANDING: Viewer should recognize the channel instantly
  - CULTURE SIGNAL: Visual cue to the tale's origin (subtle)
"""

class ThumbAgent:
    
    # Thumbnail dimensions
    WIDTH = 1280
    HEIGHT = 720     # Standard YouTube thumbnail
    SHORTS_WIDTH = 1080
    SHORTS_HEIGHT = 1920  # Shorts thumbnail (auto-cropped usually)
    
    # Channel-specific templates
    TEMPLATES = {
        "story_fire": {
            "border_color": "#8B6914",        # Warm amber
            "border_width": 12,
            "title_font": "EB Garamond",      # Elegant serif
            "title_color": "#F5E6CC",          # Warm cream
            "title_shadow": "#000000",
            "title_max_words": 5,
            "overlay_gradient": "linear: #00000000 -> #000000CC",  # Bottom fade
            "branding_position": "bottom_right",
            "branding_text": "🔥 Story Fire",
            "branding_font_size": 24,
        },
        "new_eden_whispers": {
            "border_color": None,              # No border — bleeds to edge
            "title_font": "Rajdhani",          # Sci-fi sans-serif
            "title_color": "#FFFFFF",
            "title_shadow": "#0055AA",          # Blue glow
            "title_max_words": 4,
            "overlay_gradient": "linear: #00000000 -> #0A0A2ECC",
            "branding_position": "bottom_right",
            "branding_text": "NEW EDEN WHISPERS",
            "branding_font_size": 20,
        },
        "holmes_wisdom": {
            "border_color": None,
            "title_font": "Cormorant Garamond",
            "title_color": "#E8D5B7",
            "title_shadow": "#1A0533",
            "title_max_words": 6,
            "overlay_gradient": "radial: #1A053300 -> #0A0A2ECC",
            "branding_position": "bottom_center",
            "branding_text": "HOLMES WISDOM",
            "branding_font_size": 20,
        },
    }

    async def generate_thumbnail(
        self,
        script: dict,
        scene_images: list[Path],
        channel: str,
        language: str,
    ) -> Path:
        """Generate thumbnail for a video."""
        
        template = self.TEMPLATES[channel]
        
        # Step 1: ANIMUS writes thumbnail text
        thumb_text = await self.animus.generate(
            prompt=f"""Write {template['title_max_words']} or fewer words 
for a YouTube thumbnail about this tale:

Hook: {script['hook']}
Tale: {script.get('tale_title', '')}
Culture: {script.get('culture', '')}

The text must:
- Create curiosity or intrigue
- Be readable at tiny sizes
- NOT be the tale title (too boring)
- Be in {language}

Examples of great thumbnail text:
- "She married DEATH"
- "The wolf's secret"
- "Why spiders are thin"
- "He tricked a GOD"

Output ONLY the thumbnail text, nothing else.""",
            temperature=0.8,
        )
        
        # Step 2: Select best scene image for thumbnail
        # Use the hook image (first) or most dramatic image
        base_image = self._select_best_image(scene_images)
        
        # Step 3: Composite thumbnail
        thumb = self._composite(
            base_image=base_image,
            text=thumb_text.strip(),
            template=template,
            language=language,
        )
        
        return self._save(thumb, channel, script)

    def _composite(
        self,
        base_image: Image,
        text: str,
        template: dict,
        language: str,
    ) -> Image:
        """Layer text, borders, and branding onto base image."""
        from PIL import Image, ImageDraw, ImageFont, ImageFilter
        
        img = base_image.copy()
        img = img.resize((self.WIDTH, self.HEIGHT))
        draw = ImageDraw.Draw(img)
        
        # Apply gradient overlay (bottom darkening for text readability)
        gradient = self._create_gradient(template["overlay_gradient"])
        img = Image.alpha_composite(img.convert("RGBA"), gradient)
        
        # Add border if configured
        if template.get("border_color"):
            draw.rectangle(
                [0, 0, self.WIDTH-1, self.HEIGHT-1],
                outline=template["border_color"],
                width=template["border_width"],
            )
        
        # Add title text with shadow
        font_size = self._calculate_font_size(text, template)
        font = ImageFont.truetype(
            f"assets/fonts/{template['title_font']}.ttf",
            font_size,
        )
        
        # Text shadow
        shadow_offset = max(3, font_size // 15)
        text_pos = self._center_text(text, font, img.size)
        draw.text(
            (text_pos[0] + shadow_offset, text_pos[1] + shadow_offset),
            text.upper(),
            font=font,
            fill=template["title_shadow"],
        )
        # Main text
        draw.text(
            text_pos,
            text.upper(),
            font=font,
            fill=template["title_color"],
        )
        
        # Channel branding
        brand_font = ImageFont.truetype(
            f"assets/fonts/{template['title_font']}.ttf",
            template["branding_font_size"],
        )
        draw.text(
            self._brand_position(template),
            template["branding_text"],
            font=brand_font,
            fill="#FFFFFF88",
        )
        
        return img
```

### Thumbnail A/B Testing (Future)

Once the system is running, generate 3 thumbnail variants per video:
1. **Scene focus** — dramatic scene from the tale
2. **Character focus** — close-up of a character/creature
3. **Text focus** — bold text on simple gradient

Track CTR per variant style. Feed data back to ANIMUS to refine thumbnail concepts over time.

---

## Animus — The Creative Brain

### Role

Animus is the **creative director** of the entire operation. It's not just an LLM — it's the intelligence that makes decisions about:

- Which tales to tell and when
- How to write scripts in each channel's voice
- How to adapt content for each language
- What visual scenes to generate
- What thumbnail text will hook viewers
- How to adjust strategy based on analytics

### Animus Configuration

```yaml
animus:
  engine: "ollama"
  model: "llama3.1:70b"          # Use the biggest model you can run
  fallback_model: "llama3.1:8b"  # For faster, simpler tasks
  url: "http://localhost:11434/api/generate"
  
  # Task routing — which model handles which tasks
  task_routing:
    script_generation: "llama3.1:70b"     # Needs creativity + nuance
    translation: "llama3.1:70b"            # Needs cultural understanding
    thumbnail_text: "llama3.1:8b"          # Quick, simple task
    sd_prompt_writing: "llama3.1:8b"       # Formulaic
    analytics_interpretation: "llama3.1:70b" # Needs reasoning
    quality_review: "llama3.1:70b"         # Needs judgment
    metadata_generation: "llama3.1:8b"     # Formulaic
    
  # System prompts loaded per task
  prompt_library:
    story_fire_storyteller: "prompts/story_fire_storyteller.txt"
    story_fire_dog: "prompts/story_fire_dog.txt"
    eve_chronicler: "prompts/eve_chronicler.txt"
    holmes_guide: "prompts/holmes_guide.txt"
    translator: "prompts/babel_translator.txt"
    thumbnail_writer: "prompts/thumb_writer.txt"
    analytics_analyst: "prompts/oracle_analyst.txt"
    quality_reviewer: "prompts/quality_review.txt"
```

### Quality Gate

Before any video enters the upload queue, ANIMUS reviews it:

```python
class QualityGate:
    """ANIMUS reviews generated content before distribution."""
    
    async def review_script(self, script: dict, channel: str) -> dict:
        """Review script quality. Returns pass/fail + notes."""
        review = await self.animus.generate(
            prompt=f"""Review this {channel} script for quality:

{json.dumps(script, indent=2)}

Check:
1. Does the hook create genuine curiosity? (1-10)
2. Does the narration maintain the character voice? (1-10)
3. Is the story self-contained and understandable? (1-10)
4. Is the closing satisfying or intriguing? (1-10)
5. Is the word count appropriate (100-140 words)? (pass/fail)
6. Any problematic content? (pass/flag)

Respond as JSON: {{scores: {{...}}, overall: 1-10, pass: true/false, notes: "..."}}
Minimum passing score: 7/10 overall.""",
            temperature=0.3,  # Low temp for consistent evaluation
        )
        return json.loads(review)
    
    async def review_translation(
        self, original: dict, translated: dict, language: str
    ) -> dict:
        """Verify translation quality and cultural adaptation."""
        review = await self.animus.generate(
            prompt=f"""Compare this original English script with its 
{language} translation. Verify:

1. Meaning preserved? (1-10)
2. Cultural adaptation appropriate? (1-10)  
3. Character voices maintained? (1-10)
4. Word count within 10% of original? (pass/fail)
5. Vocal cues [pause] etc preserved? (pass/fail)

Original: {json.dumps(original, indent=2)}
Translation: {json.dumps(translated, indent=2)}

JSON response only.""",
            temperature=0.3,
        )
        return json.loads(review)
```

---

## Gorgon Agent Specifications

### Agent Registry

```yaml
# gorgon_agents.yaml — Master agent configuration

agents:
  # ── CREATIVE LAYER ──
  
  bard:
    description: "Script extraction and writing"
    depends_on: ["animus"]
    gpu_required: false
    restart_on_failure: true
    max_retries: 3
    timeout: 120
    
  babel:
    description: "Multi-language translation and adaptation"
    depends_on: ["animus", "bard"]
    gpu_required: false
    restart_on_failure: true
    max_retries: 3
    timeout: 90
    
  # ── PRODUCTION LAYER ──
    
  voice:
    description: "Epic TTS narration generation"
    depends_on: ["babel"]
    gpu_required: false  # ElevenLabs is cloud
    restart_on_failure: true
    max_retries: 2
    timeout: 60
    rate_limit: "10 requests/minute"  # ElevenLabs rate limit
    
  painter:
    description: "Visual scene generation via Stable Diffusion"
    depends_on: ["bard"]  # Only needs original script, not translations
    gpu_required: true
    vram_minimum: "8GB"
    restart_on_failure: true
    max_retries: 2
    timeout: 300  # SD can be slow
    
  thumb:
    description: "Thumbnail generation"
    depends_on: ["painter", "animus"]
    gpu_required: false  # Compositing only
    restart_on_failure: true
    
  scribe:
    description: "Caption generation via Whisper"
    depends_on: ["voice"]
    gpu_required: true  # Whisper benefits from GPU
    restart_on_failure: true
    timeout: 60
    
  weaver:
    description: "Final video assembly via FFmpeg"
    depends_on: ["voice", "painter", "scribe"]
    gpu_required: false
    restart_on_failure: true
    timeout: 120
    
  # ── DISTRIBUTION LAYER ──
    
  keeper:
    description: "Content calendar and tale selection"
    depends_on: ["animus"]
    gpu_required: false
    schedule: "daily at 02:00"  # Plan tomorrow's content overnight
    
  herald:
    description: "YouTube upload and metadata"
    depends_on: ["weaver", "thumb"]
    gpu_required: false
    restart_on_failure: true
    rate_limit: "50 uploads/day"  # YouTube API limit
    
  oracle:
    description: "Analytics collection and strategy adjustment"
    depends_on: ["animus"]
    gpu_required: false
    schedule: "daily at 01:00"  # Collect yesterday's data overnight
    
  quality_gate:
    description: "Content quality review before publishing"
    depends_on: ["animus"]
    gpu_required: false
    blocks: ["herald"]  # Must pass before upload
```

### Execution Pipeline

```python
"""
Gorgon execution pipeline for a single tale.

Demonstrates parallelism: visuals and translations run concurrently.
"""

async def produce_tale(tale: Tale, channel: str, languages: list[str]):
    """Full production pipeline for one tale across all languages."""
    
    # Phase 1: Script (sequential — needs to complete first)
    script = await gorgon.run_agent("bard", tale=tale, channel=channel)
    
    # Quality gate on script
    review = await gorgon.run_agent("quality_gate", script=script)
    if not review["pass"]:
        log.warning(f"Script failed quality gate: {review['notes']}")
        return None
    
    # Phase 2: Parallel production
    # Visuals only need to generate ONCE (language-independent)
    # Translations can run in parallel for all languages
    
    visual_task = gorgon.run_agent("painter", script=script, channel=channel)
    thumb_concept_task = gorgon.run_agent("thumb", script=script, channel=channel, step="concept")
    
    translation_tasks = {
        lang: gorgon.run_agent("babel", script=script, language=lang, channel=channel)
        for lang in languages if lang != "en"
    }
    
    # Wait for visuals (shared across all languages)
    scene_images = await visual_task
    
    # Wait for all translations
    translated_scripts = {"en": script}
    for lang, task in translation_tasks.items():
        translated_scripts[lang] = await task
    
    # Phase 3: Per-language production (parallel across languages)
    upload_queue = []
    
    for lang in languages:
        lang_script = translated_scripts[lang]
        
        # These run in parallel per language
        audio = await gorgon.run_agent("voice", 
            script=lang_script, language=lang, channel=channel)
        
        captions = await gorgon.run_agent("scribe",
            audio=audio, language=lang)
        
        thumbnail = await gorgon.run_agent("thumb",
            script=lang_script, images=scene_images, 
            channel=channel, language=lang)
        
        # Assembly (uses shared visuals + language-specific audio/captions)
        video = await gorgon.run_agent("weaver",
            images=scene_images, audio=audio, 
            captions=captions, channel=channel)
        
        # Queue for upload
        upload_queue.append({
            "video": video,
            "thumbnail": thumbnail,
            "metadata": self._build_metadata(lang_script, lang, channel),
            "language": lang,
            "channel": channel,
        })
    
    # Phase 4: Distribution
    for item in upload_queue:
        await gorgon.run_agent("herald", **item)
    
    return upload_queue
```

---

## Autonomous Distribution System

### The HERALD Agent — YouTube Upload

```python
"""
HERALD Agent — Automated YouTube publishing.

Handles:
  - YouTube Data API v3 upload
  - Localized metadata (title, description, tags) per language
  - Scheduled publishing times per timezone/language
  - Thumbnail upload
  - Playlist management
  - Shorts-specific settings
"""

class HeraldAgent:
    
    # Optimal posting times by language/region
    POSTING_SCHEDULE = {
        "en": "08:00 America/Los_Angeles",    # US morning
        "es": "09:00 America/Mexico_City",     # LatAm morning  
        "fr": "08:00 Europe/Paris",            # France morning
        "de": "08:00 Europe/Berlin",           # Germany morning
        "pt": "09:00 America/Sao_Paulo",       # Brazil morning
        "ja": "08:00 Asia/Tokyo",              # Japan morning
        "hi": "09:00 Asia/Kolkata",            # India morning
        "ar": "09:00 Asia/Riyadh",             # Middle East morning
        "ru": "09:00 Europe/Moscow",           # Russia morning
    }
    
    async def publish(
        self,
        video: Path,
        thumbnail: Path,
        metadata: dict,
        language: str,
        channel: str,
    ):
        """Upload and schedule a video on YouTube."""
        
        schedule_time = self._calculate_publish_time(language)
        
        body = {
            "snippet": {
                "title": metadata["title"],
                "description": metadata["description"],
                "tags": metadata["tags"],
                "categoryId": "24",  # Entertainment (or 27 for Education)
                "defaultLanguage": language,
                "defaultAudioLanguage": language,
            },
            "status": {
                "privacyStatus": "private",  # Set to public at scheduled time
                "publishAt": schedule_time.isoformat(),
                "selfDeclaredMadeForKids": False,
                "shorts": {"shortsEnabled": True},
            },
        }
        
        # Upload video
        video_id = await self.youtube_api.upload(video, body)
        
        # Upload thumbnail
        await self.youtube_api.set_thumbnail(video_id, thumbnail)
        
        # Add to appropriate playlist
        playlist_id = self._get_playlist(channel, language, metadata)
        await self.youtube_api.add_to_playlist(video_id, playlist_id)
        
        log.info(f"Scheduled: {metadata['title']} [{language}] → {schedule_time}")
        
        return video_id
```

### Metadata Generation (via ANIMUS)

```python
async def generate_metadata(
    self, script: dict, language: str, channel: str
) -> dict:
    """Generate localized YouTube metadata."""
    
    channel_configs = {
        "story_fire": {
            "title_template": '"{hook_short}" — {culture} Folk Tale | Story Fire',
            "base_tags": ["folklore", "fairy tales", "mythology", 
                         "storytelling", "Story Fire"],
            "category": "Entertainment",
        },
        "new_eden_whispers": {
            "title_template": '"{hook_short}" | EVE Online Lore',
            "base_tags": ["EVE Online", "EVE lore", "New Eden", 
                         "gaming lore", "sci-fi"],
            "category": "Gaming",
        },
        "holmes_wisdom": {
            "title_template": '"{hook_short}" — Ernest Holmes | Holmes Wisdom',
            "base_tags": ["Science of Mind", "Ernest Holmes", 
                         "spiritual wisdom", "new thought"],
            "category": "Education",
        },
    }
    
    config = channel_configs[channel]
    
    # ANIMUS generates localized metadata
    metadata = await self.animus.generate(
        prompt=f"""Generate YouTube metadata in {language} for this video:

Channel: {channel}
Script hook: {script['hook']}
Tale: {script.get('tale_title', '')}
Culture: {script.get('culture', '')}
Themes: {script.get('themes', [])}

Generate:
1. title: Intriguing, {language}-native, under 70 characters
2. description: 3-4 lines in {language}, include source credit and channel info
3. tags: 15-20 relevant tags in {language}

JSON format only.""",
        temperature=0.7,
    )
    
    result = json.loads(metadata)
    
    # Append standard tags
    result["tags"].extend(config["base_tags"])
    
    # Add AI disclosure
    result["description"] += f"\n\n🤖 AI-assisted narration and illustrations.\n"
    result["description"] += "All stories from the public domain oral tradition."
    
    return result
```

---

## Content Strategy & Scheduling

### The KEEPER Agent — Autonomous Content Planner

```python
"""
KEEPER Agent — Content calendar and tale selection.

Runs daily to plan the next day's content across all channels.
Uses analytics feedback to optimize selections.

Decision factors:
  1. Cultural rotation (don't repeat same culture back-to-back)
  2. Mood balance (mix light and dark across the week)
  3. Performance data (which cultures/moods get most views)
  4. Seasonal relevance (Norse in winter, Japanese cherry blossom season, etc.)
  5. Cross-promotion potential (tales that complement each other)
  6. Never repeat a tale within 6 months
"""

class KeeperAgent:
    
    async def plan_tomorrow(self, analytics: dict) -> list[dict]:
        """Plan all content for tomorrow across all channels."""
        
        plan = []
        
        # Story Fire — select folklore tale
        sf_tale = await self._select_tale(
            channel="story_fire",
            analytics=analytics.get("story_fire", {}),
            constraints={
                "culture_rotation": self._get_recent_cultures("story_fire"),
                "mood_balance": self._get_week_moods("story_fire"),
                "seasonal": self._get_seasonal_themes(),
                "exclude_recent": self._get_told_tales(months=6),
            }
        )
        plan.append({"channel": "story_fire", "tale": sf_tale})
        
        # New Eden Whispers — select chronicle
        new_tale = await self._select_tale(
            channel="new_eden_whispers",
            analytics=analytics.get("new_eden_whispers", {}),
            constraints={
                "faction_rotation": self._get_recent_factions(),
                "mood_balance": self._get_week_moods("new_eden_whispers"),
            }
        )
        plan.append({"channel": "new_eden_whispers", "tale": new_tale})
        
        # Holmes Wisdom — select passage
        hw_passage = await self._select_tale(
            channel="holmes_wisdom",
            analytics=analytics.get("holmes_wisdom", {}),
            constraints={
                "theme_rotation": self._get_recent_themes("holmes_wisdom"),
            }
        )
        plan.append({"channel": "holmes_wisdom", "tale": hw_passage})
        
        return plan
    
    async def _select_tale(self, channel: str, analytics: dict, constraints: dict) -> Tale:
        """ANIMUS selects the optimal tale given constraints and performance data."""
        
        # Get candidate tales
        candidates = self.tale_database.get_candidates(
            channel=channel,
            exclude=constraints.get("exclude_recent", []),
        )
        
        # ANIMUS makes the selection
        selection = await self.animus.generate(
            prompt=f"""Select the best tale for tomorrow's {channel} video.

Performance data from last 30 days:
- Top performing cultures: {analytics.get('top_cultures', 'N/A')}
- Top performing moods: {analytics.get('top_moods', 'N/A')}
- Average view count: {analytics.get('avg_views', 'N/A')}
- Best performing day of week: {analytics.get('best_day', 'N/A')}

Constraints:
- Recent cultures used: {constraints.get('culture_rotation', [])}
- This week's moods so far: {constraints.get('mood_balance', [])}
- Seasonal relevance: {constraints.get('seasonal', 'none')}

Available candidates (top 20):
{self._format_candidates(candidates[:20])}

Select ONE tale. Explain your reasoning briefly.
Format: {{"tale_id": "...", "reason": "..."}}""",
            temperature=0.6,
        )
        
        return self.tale_database.get(json.loads(selection)["tale_id"])
```

---

## Analytics & Feedback Loop

### The ORACLE Agent

```python
"""
ORACLE Agent — Analytics collection and strategy interpretation.

Collects YouTube Analytics API data daily.
Interprets trends and feeds back to KEEPER and ANIMUS.
"""

class OracleAgent:
    
    TRACKED_METRICS = {
        "views": "per video, per language, per culture",
        "watch_time": "average percentage viewed",
        "ctr": "click-through rate from impressions",
        "subscribers_gained": "per video attribution",
        "shares": "per video",
        "likes_ratio": "likes / (likes + dislikes)",
    }
    
    async def daily_report(self) -> dict:
        """Generate daily performance report across all channels."""
        
        data = {}
        for channel in ["story_fire", "new_eden_whispers", "holmes_wisdom"]:
            channel_data = await self.youtube_analytics.fetch(
                channel_id=self.channel_ids[channel],
                metrics=list(self.TRACKED_METRICS.keys()),
                period="last_7_days",
            )
            
            data[channel] = {
                "top_cultures": self._rank_by_metric(channel_data, "culture", "views"),
                "top_moods": self._rank_by_metric(channel_data, "mood", "views"),
                "top_languages": self._rank_by_metric(channel_data, "language", "views"),
                "avg_views": self._average(channel_data, "views"),
                "avg_ctr": self._average(channel_data, "ctr"),
                "avg_retention": self._average(channel_data, "watch_time"),
                "best_day": self._best_day(channel_data),
                "best_posting_time": self._best_time(channel_data),
                "trending_up": self._trending(channel_data, "up"),
                "trending_down": self._trending(channel_data, "down"),
            }
        
        # ANIMUS interprets the data
        interpretation = await self.animus.generate(
            prompt=f"""Analyze this weekly performance data and provide 
strategic recommendations:

{json.dumps(data, indent=2)}

Provide:
1. What's working (double down)
2. What's underperforming (adjust or drop)
3. Language expansion recommendations
4. Content strategy adjustments
5. Thumbnail/title patterns that correlate with high CTR

JSON format with actionable items.""",
            temperature=0.4,
        )
        
        return {
            "raw_data": data,
            "interpretation": json.loads(interpretation),
            "generated_at": datetime.now().isoformat(),
        }
```

---

## Infrastructure & Cost

### Hardware Requirements

| Component | Minimum | Recommended | Notes |
|-----------|---------|-------------|-------|
| CPU | Modern 8-core | 12+ core | FFmpeg assembly, orchestration |
| RAM | 16GB | 32GB | Ollama + SD simultaneous |
| GPU | RTX 3060 (12GB) | RTX 4070+ (12GB+) | SD image gen + Whisper |
| Storage | 500GB SSD | 1TB NVMe | Source texts, generated assets, output |
| Internet | 50 Mbps up | 100+ Mbps up | 16 video uploads/day |

### Monthly Cost Projection

| Item | Free Option | Paid Option | Notes |
|------|-------------|-------------|-------|
| Ollama (Animus) | $0 | $0 | Local |
| Stable Diffusion | $0 | $0 | Local GPU |
| Whisper | $0 | $0 | Local |
| FFmpeg | $0 | $0 | Local |
| Piper TTS | $0 | — | Decent but not epic |
| **ElevenLabs** | — | **$22/mo** (Creator) | 100K chars/mo — covers ~100 videos |
| **ElevenLabs** | — | **$99/mo** (Pro) | 500K chars/mo — covers ~480 videos |
| YouTube API | $0 | $0 | Free tier sufficient |
| Domain | — | $12/yr | Optional |
| **TOTAL (MVP)** | **$0** | | Piper TTS only |
| **TOTAL (Production)** | | **$22-99/mo** | ElevenLabs is the real cost |

**The cost calculation for ElevenLabs:**
- Average script: ~130 words ≈ 700 characters
- 16 videos/day × 700 chars = 11,200 chars/day
- Monthly: ~336,000 characters
- Creator plan (100K chars) insufficient for full operation
- **Pro plan ($99/mo) covers it** with headroom for retakes
- Alternative: Use ElevenLabs for English only, Coqui XTTS (free, local) for other languages

**Cost-optimized approach:**
```
English narration:  ElevenLabs ($22/mo Creator plan — EN only = ~30K chars)
Other languages:    Coqui XTTS (free, local, voice cloning)
Total:              $22/mo
```

### Electricity & Compute

Running SD + Ollama + Whisper for ~4-6 hours daily generation:
- ~300W GPU + ~200W system = 500W
- 5 hours/day × 30 days = 150 hours
- 150 hours × 0.5 kW = 75 kWh/month
- At $0.12/kWh = **~$9/month** in electricity

**True total cost: ~$31/month** for a fully autonomous system producing 480 videos/month.

---

## Build Order & Timeline

### Phase 0: Foundation (Week 1)

```
□ Gorgon core — agent lifecycle, shared state, task queue
□ Animus setup — Ollama model, prompt library, task routing
□ Directory structure and configuration system
□ Basic logging and health monitoring
```

### Phase 1: Story Fire MVP in English (Week 2-3)

```
□ Source library — download & preprocess 50 folk tales
□ BARD agent — script extraction with Storyteller voice
□ VOICE agent — single voice (Storyteller only, Piper TTS)
□ PAINTER agent — SD visual generation with culture palettes
□ SCRIBE agent — Whisper captions
□ WEAVER agent — FFmpeg assembly
□ Quality gate — ANIMUS script review
□ FIRST SHORT PRODUCED AND REVIEWED
```

### Phase 2: Upgrade Voice & Add Dog (Week 3-4)

```
□ ElevenLabs integration — epic Storyteller voice
□ Dog voice — second character narration
□ Two-voice audio compositing
□ Fire crackle ambient layer
□ Visual refinement — post-processing, Ken Burns
```

### Phase 3: Thumbnails & Distribution (Week 4-5)

```
□ THUMB agent — automated thumbnail generation
□ HERALD agent — YouTube API upload
□ KEEPER agent — content calendar
□ Metadata generation — titles, descriptions, tags
□ LAUNCH STORY FIRE ENGLISH CHANNEL
```

### Phase 4: Multi-Language (Week 5-7)

```
□ BABEL agent — translation/adaptation system
□ Spanish narration (ElevenLabs or Coqui)
□ 3 additional languages
□ Per-language metadata generation
□ Posting schedule optimization per timezone
□ LAUNCH MULTI-LANGUAGE STORY FIRE
```

### Phase 5: Second Channel — New Eden Whispers (Week 7-9)

```
□ Chronicle scraper
□ EVE Chronicler voice profile
□ Faction-specific visual palettes
□ EVE-specific thumbnail style
□ 4-language setup (EN, ES, DE, RU)
□ LAUNCH NEW EDEN WHISPERS
```

### Phase 6: Third Channel — Holmes Wisdom (Week 9-10)

```
□ Holmes source text preprocessing
□ Guide voice profile
□ Ethereal visual style
□ 4-language setup (EN, ES, PT, FR)
□ LAUNCH HOLMES WISDOM
```

### Phase 7: Analytics & Optimization (Week 10+)

```
□ ORACLE agent — YouTube Analytics API integration
□ Performance tracking per culture, mood, language
□ ANIMUS-driven strategy adjustment
□ Thumbnail A/B testing
□ Content calendar optimization
□ FULLY AUTONOMOUS LOOP ACHIEVED
```

### Phase 8: Livestream Layer (Week 12+)

```
□ MUSE agent — real-time music generation
□ IRIS agent — real-time visual morphing
□ HERMES agent — chat interaction
□ CHRONOS agent — time-based scheduling
□ Story Fire Radio (24/7 livestream)
□ New Eden Radio (24/7 livestream)
```

---

## Operational Runbook

### Daily Autonomous Cycle

```
01:00  ORACLE collects yesterday's analytics
02:00  KEEPER plans today's content (informed by ORACLE)
03:00  BARD generates scripts for all 3 channels
03:30  Quality gate reviews scripts
04:00  BABEL translates scripts into all target languages
05:00  PAINTER generates visuals (shared across languages)
05:30  THUMB generates thumbnails
06:00  VOICE generates narration (all languages, all channels)
07:00  SCRIBE generates captions
07:30  WEAVER assembles final videos
08:00  HERALD begins scheduled uploads (per timezone)
        └── EN uploads at 08:00 PT
        └── ES uploads at 09:00 CT
        └── FR/DE uploads at 08:00 CET
        └── JA uploads at 08:00 JST
        └── etc.
```

**Total compute time: ~6-7 hours overnight**
**Human intervention: ZERO (review weekly analytics report)**

### Weekly Human Review

Even with full automation, spend 30 minutes weekly:
1. Review ORACLE's weekly report
2. Spot-check 3-5 random Shorts for quality
3. Review any flagged content from quality gate
4. Approve/adjust KEEPER's strategy recommendations
5. Check channel health (strikes, claims, etc.)

### Emergency Procedures

```yaml
agent_failure:
  action: "Gorgon auto-restarts failed agent (max 3 retries)"
  escalation: "If 3 retries fail, skip that video, alert via email/Discord"

youtube_api_failure:
  action: "Queue videos locally, retry upload every 30 minutes"
  escalation: "If 24hr backlog, alert for manual review"

quality_gate_rejection:
  action: "BARD regenerates script with ANIMUS feedback"
  escalation: "If 3 regenerations fail, skip tale, log for review"

copyright_claim:
  action: "Alert immediately — all folklore is PD but mistakes happen"
  escalation: "Human review required within 24 hours"
```

---

## The Portfolio Pitch

When you're in interviews for AI enablement roles, here's the elevator pitch:

> *"I designed and built an autonomous multi-agent AI system called Gorgon that orchestrates real-time content generation across three YouTube channels in eight languages. The system uses a local LLM as its creative director, coordinates six specialized AI agents for script generation, multi-language adaptation, visual generation, voice synthesis, and automated distribution — producing 480 videos per month with zero human intervention. The channels are live and generating revenue."*

That's not a side project. That's a **production AI system** demonstrating:
- Multi-agent orchestration
- LLM-driven creative decision making
- Multi-modal AI integration (text, image, audio, video)
- Autonomous scheduling and distribution
- Analytics-driven feedback loops
- Cross-language adaptation at scale

**This is what companies like Palantir, Scale AI, and Glean hire for.**

---

*Built by ARETE — One framework. Three channels. Eight languages. Zero bottleneck.*
*Powered by Gorgon. Directed by Animus.*
