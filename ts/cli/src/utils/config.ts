import fs from "fs";
import os from "os";
import path from "path";

/** Decide once – use everywhere */
function resolveConfigDir(): string {
  // For tests or advanced setups you can override the dir
  if (process.env.BERNERSPACE_CONFIG_DIR)
    return process.env.BERNERSPACE_CONFIG_DIR;

  if (process.platform === "win32") {
    // %APPDATA%\bernerspace (e.g. C:\Users\<you>\AppData\Roaming\bernerspace)
    return path.join(
      process.env.APPDATA ?? path.join(os.homedir(), "AppData", "Roaming"),
      "bernerspace"
    );
  }

  if (process.platform === "darwin") {
    // Keep the original hidden folder on macOS for backwards‑compat
    return path.join(os.homedir(), ".bernerspace");
  }

  // Linux / BSD – follow XDG if present, else ~/.config
  const base =
    process.env.XDG_CONFIG_HOME ?? path.join(os.homedir(), ".config");
  return path.join(base, "bernerspace");
}

export const CONFIG_DIR = resolveConfigDir();
export const CONFIG_FILE = path.join(CONFIG_DIR, "config.json");

export interface UserConfig {
  token: string;
  email: string;
  username?: string;
  avatar_url?: string;
}

export function saveConfig(config: UserConfig) {
  fs.mkdirSync(CONFIG_DIR, { recursive: true });
  fs.writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2));
}

export function loadConfig(): UserConfig {
  if (!fs.existsSync(CONFIG_FILE)) throw new Error("ConfigNotInitialized");
  return JSON.parse(fs.readFileSync(CONFIG_FILE, "utf-8"));
}
