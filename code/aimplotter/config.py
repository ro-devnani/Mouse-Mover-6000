from dataclasses import dataclass, field


@dataclass
class Config:
    # --- display ---
    screen_region: dict = field(
        default_factory=lambda: {"top": 0, "left": 0, "width": 1920, "height": 1080}
    )
    screen_center: tuple[int, int] = (960, 540)
    capture_backend: str = "auto"   # auto | dxcam | mss

    # --- detection (neon blue in HSV; OpenCV H is 0-179) ---
    hsv_lower: tuple[int, int, int] = (90, 120, 120)
    hsv_upper: tuple[int, int, int] = (120, 255, 255)
    min_area_px: float = 80.0

    # --- control ---
    gain: float = 0.24            # mm of plotter travel per px of error (calibrated, same-target)
    kp: float = 1.0               # multiplies gain
    ki: float = 0.0               # 0 = pure PD
    kd: float = 0.5
    max_move_mm: float = 6.0      # clamp per frame -> "glide"
    move_settle_s: float = 0.04   # wait after a jog for the view to render before re-capture
    debug: bool = True           # print per-frame error + move
    hitbox_tol_px: float = 6.0    # hold zone = ball radius + this; smaller = centers tighter
    invert_x: bool = False        # flip if +X move turns view the wrong way
    invert_y: bool = True         # +Y=mouse up=look up=targets slide down (inverted)

    # --- velocity control (smooth streaming system) ---
    kp_v: float = 0.8             # mm/s commanded speed per px of error
    kff: float = 0.0              # feedforward scale on target pixel motion (0 = off; noise amp at high fps)
    max_speed_mm_s: float = 120.0  # velocity magnitude clamp
    vel_watchdog_ms: int = 600    # firmware halts if no V within this window
    vel_deadzone_tol_px: float = 6.0  # hold zone = ball radius + this

    # --- plotter / serial ---
    port: str = "COM6"
    baud: int = 115200
    press_angle: int = 60         # servo degrees when clicking
    release_angle: int = 90       # servo degrees at rest
    click_dwell_s: float = 0.04

    # --- soft limits (mm), bed center is origin reference ---
    soft_limit_mm: float = 90.0   # +/- travel from center (200mm range, 10mm margin)
    bed_center_mm: tuple[float, float] = (0.0, 0.0)

    # --- drift corrector ---
    drift_idle_frames: int = 8
    drift_step_mm: float = 1.0

    # --- tracking (stable target IDs) ---
    track_match_dist_px: float = 80.0   # max move to keep same ID
    track_max_misses: int = 5           # lost-frame grace

    # --- safety ---
    kill_key: str = "q"
