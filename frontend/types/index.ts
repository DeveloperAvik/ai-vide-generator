export type Status = "TOPIC_PENDING" | "RESEARCHING" | "SCRIPT_GENERATED" | "TECHNICAL_REVIEW" | "SCRIPT_APPROVED" | "ASSETS_GENERATING" | "ASSETS_READY"
  | "RENDERING" | "QUALITY_CHECK" | "APPROVAL_PENDING" | "APPROVED" | "SCHEDULED" | "PUBLISHED" | "FAILED";
export interface Lesson { id: number; module_id: number; position: number; title: string; summary: string; status: Status; retry_count: number; last_error: string; estimated_minutes: number; draft?: boolean; updated_at: string }
export interface Module { id: number; course_id: number; title: string; description: string; position: number; lessons: Lesson[] }
export interface Course { id: number; name: string; description: string; difficulty: string; language: string; domain?: string; videos_per_week: number; duration_minutes: number; learning_objectives: string[]; prerequisites: string[]; modules?: Module[] }
export interface Scene { scene_id: string; type: string; duration_seconds: number; narration: string; visual_description: string; on_screen_text: string; asset_requirements: string[]; transition: string; [k: string]: unknown }
export interface Render { id: number; lesson_id: number; status: string; progress: number; duration: number; error: string; engine: string; stage?: RenderStage; scenes?: RenderScene[] }
export type RenderStage = "script" | "scenes" | "images" | "voice" | "video" | "finalize";
/** Optional: the API does not return these today; the UI renders them only when present. */
export interface RenderScene { scene_id: string; status: "pending" | "active" | "done"; thumbnail_url?: string }
