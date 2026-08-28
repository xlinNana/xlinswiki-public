import type { FullSlug } from "./path"

interface SluggableData {
  slug?: FullSlug
  aliases?: FullSlug[]
  frontmatter?: Record<string, unknown>
}

const PUBLICATION_SLUG = /^\d{6}$/

export function applyFrontmatterSlug(fileData: SluggableData): void {
  const currentSlug = fileData.slug
  const configured = fileData.frontmatter?.slug
  if (!currentSlug || currentSlug === "index" || configured == null || configured === "") return

  const canonical = configured.toString().trim().toLowerCase()
  if (!PUBLICATION_SLUG.test(canonical)) {
    throw new Error(`frontmatter slug must be exactly six digits: ${configured}`)
  }

  const aliases = fileData.aliases ?? []
  if (currentSlug !== canonical && !aliases.includes(currentSlug)) {
    aliases.push(currentSlug)
  }
  fileData.aliases = aliases
  fileData.slug = canonical as FullSlug
}
