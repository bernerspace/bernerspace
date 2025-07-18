import fs from "fs";
export default function detectLanguage(): string {
  if (fs.existsSync("package.json")) {
    const pkg = JSON.parse(fs.readFileSync("package.json", "utf-8"));
    return pkg.devDependencies?.typescript ? "typescript" : "javascript";
  }
  if (fs.existsSync("requirements.txt")) return "python";
  return "unknown";
}
