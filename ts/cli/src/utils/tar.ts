// src/utils/tar.ts
import { spawnSync } from "child_process";
import fs from "fs";
import path from "path";

/**
 * Create a tarball of the current directory named <projectName>.tar
 * Excludes
 *  • patterns in .gitignore
 *  • node_modules/
 *  • Python virtual envs (venv/ .venv / __pycache__)
 *  • the archive file itself
 *
 * @param projectName   The human‑readable project name, e.g. "My API"
 * @returns             Full path to the created tar file
 */
export function packDirectory(projectName: string): string {
  const cwd = process.cwd();

  // slug‑ify the project name: spaces → dashes, lower‑case, no funky chars
  const slug = projectName
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "-") // spaces to dashes
    .replace(/[^a-z0-9._-]/g, ""); // remove anything unsafe for filenames

  const name = `${slug}.tar.gz`;
  const output = path.join(cwd, name);

  const excludes: string[] = [];

  // Respect .gitignore if present
  const gi = path.join(cwd, ".gitignore");
  if (fs.existsSync(gi)) {
    excludes.push(`--exclude-from=${gi}`);
  }

  // Always skip heavy or virtual‑env dirs
  ["node_modules", "venv", ".venv", "__pycache__"].forEach((pat) =>
    excludes.push(`--exclude=${pat}`)
  );

  // Skip the archive itself (important when re‑running)
  excludes.push(`--exclude=${name}`);

  // tar -c: create, -z: gzip, -f: output file
  const args = ["-czf", output, ...excludes, "."];

  const res = spawnSync("tar", args, { cwd, stdio: "inherit" });
  if (res.status !== 0) {
    console.error("❌ Error creating tarball");
    process.exit(1);
  }

  return output;
}
