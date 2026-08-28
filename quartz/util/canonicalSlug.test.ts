import assert from "node:assert/strict"
import { describe, test } from "node:test"
import { applyFrontmatterSlug } from "./canonicalSlug"
import type { FullSlug } from "./path"

function data(slug: string, frontmatter?: Record<string, unknown>) {
  return { slug: slug as FullSlug, frontmatter, aliases: [] as FullSlug[] }
}

describe("applyFrontmatterSlug", () => {
  test("promotes a six-digit frontmatter slug and retains the file path as an alias", () => {
    const fileData = data("游戏拆解/文章", { slug: "082707" })

    applyFrontmatterSlug(fileData)

    assert.equal(fileData.slug, "082707")
    assert.deepEqual(fileData.aliases, ["游戏拆解/文章"])
  })

  test("leaves the index page on the root URL", () => {
    const fileData = data("index", { slug: "082700" })

    applyFrontmatterSlug(fileData)

    assert.equal(fileData.slug, "index")
    assert.deepEqual(fileData.aliases, [])
  })

  test("rejects malformed publication slugs", () => {
    const fileData = data("note", { slug: "article-name" })

    assert.throws(() => applyFrontmatterSlug(fileData), /six digits/)
  })
})
