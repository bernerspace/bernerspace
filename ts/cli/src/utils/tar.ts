// src/utils/tar.ts
import { spawnSync } from "child_process";
import fs from "fs";
import path from "path";

/**
 * Create a hidden tarball of the current directory,
 * excluding:
 *  • entries in .gitignore
 *  • node_modules/
 *  • Python virtual envs (venv/ .venv / __pycache__)
 *  • the archive file itself
 *
 * @returns the full path to the created .tar file
 */
export function packDirectory(): string {
  const cwd = process.cwd();
  const name = `.deploy-${Date.now()}.tar`;
  const output = path.join(cwd, name);

  const excludes: string[] = [];

  // If .gitignore exists, tell tar to skip those patterns
  const gi = path.join(cwd, ".gitignore");
  if (fs.existsSync(gi)) {
    excludes.push(`--exclude-from=${gi}`);
  }

  // Always skip these
  ["node_modules", "venv", ".venv", "__pycache__"].forEach((pat) => {
    excludes.push(`--exclude=${pat}`);
  });

  // Also skip the archive file itself
  excludes.push(`--exclude=${name}`);

  // Build tar args
  // - c: create, - z: gzip, - f: output file
  const args = ["-czf", output, ...excludes, "."];

  const res = spawnSync("tar", args, { cwd, stdio: "inherit" });
  if (res.status !== 0) {
    console.error("Error creating tarball");
    process.exit(1);
  }

  return output;
}
