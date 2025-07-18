// src/commands/init.ts
import { Command } from "commander";
import inquirer from "inquirer";
import axios from "axios";
import FormData from "form-data";
import fs from "fs";
import path from "path";
import { saveConfig, loadConfig } from "../utils/config";
import { packDirectory } from "../utils/tar";
import detectLanguage from "../utils/detectLanguage";
import { API_BASE } from "../config/api";

const prompt = inquirer.createPromptModule();

interface MetadataAnswers {
  current_path: string;
  language: string;
  has_dockerfile: boolean;
}

const init = new Command("init")
  .description("Initialize (once), then create/select project & upload")
  .action(async () => {
    // 1) Load or prompt credentials
    let token: string, email: string;
    try {
      ({ token, email } = loadConfig());
    } catch {
      const creds = await prompt<{ token: string; email: string }>([
        { type: "input", name: "token", message: "Enter your API token:" },
        { type: "input", name: "email", message: "Enter your email:" }
      ]);
      token = creds.token;
      email = creds.email;
      saveConfig(token, email);
      console.log("\nConfiguration saved.\n");
    }

    // 2) Create or select project
    console.log("1) Create new project");
    console.log("2) Select existing project\n");
    const { action } = await prompt<{ action: string }>([
      {
        type: "input",
        name: "action",
        message: "Enter choice (1 or 2):",
        validate: (v) => ["1", "2"].includes(v) || "Please enter 1 or 2"
      }
    ]);

    let projectId: string;
    if (action === "1") {
      // create
      const { name } = await prompt<{ name: string }>([
        { type: "input", name: "name", message: "Project name:" }
      ]);
      const res = await axios.post(
        `${API_BASE}/projects/`,
        { name },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      projectId = res.data.id;
      console.log(`\nCreated project ${res.data.name} (ID: ${projectId})\n`);
    } else {
      // select
      const res = await axios.get(`${API_BASE}/projects/`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const projects: any[] = res.data;
      console.log("Projects:");
      projects.forEach((p, i) => console.log(`  ${i + 1}) ${p.name}`));
      console.log("");
      const { num } = await prompt<{ num: string }>([
        {
          type: "input",
          name: "num",
          message: `Select project (1-${projects.length}):`,
          validate: (v) => {
            const n = Number(v);
            return (
              (Number.isInteger(n) && n >= 1 && n <= projects.length) ||
              `Enter a number between 1 and ${projects.length}`
            );
          }
        }
      ]);
      const idx = Number(num) - 1;
      projectId = projects[idx].id;
      console.log(
        `\nSelected project ${projects[idx].name} (ID: ${projectId})\n`
      );
    }

    // 3) Gather core metadata
    const defaults = {
      current_path: ".",
      language: detectLanguage(),
      has_dockerfile: fs.existsSync("Dockerfile")
    };
    const core = await prompt<MetadataAnswers>([
      {
        type: "input",
        name: "current_path",
        message: "Current path:",
        default: defaults.current_path
      },
      {
        type: "input",
        name: "language",
        message: "Language:",
        default: defaults.language
      },
      {
        type: "confirm",
        name: "has_dockerfile",
        message: "Has Dockerfile?",
        default: defaults.has_dockerfile
      }
    ]);

    // 4) Gather env vars by key
    const { env_keys } = await prompt<{ env_keys: string }>([
      {
        type: "input",
        name: "env_keys",
        message: "Env var keys (comma separated, e.g. KEY1,KEY2):",
        default: ""
      }
    ]);
    const envVars: Record<string, string> = {};
    const keys = env_keys
      .split(",")
      .map((k) => k.trim())
      .filter((k) => k);
    for (const key of keys) {
      const { value } = await prompt<{ value: string }>([
        {
          type: "input",
          name: "value",
          message: `Value for ${key}:`
        }
      ]);
      envVars[key] = value;
    }

    // 5) Package & upload
    const tarName = packDirectory(); // now returns hidden .deploy-XXXX.tar
    const form = new FormData();
    form.append("file", fs.createReadStream(tarName));
    form.append("current_path", core.current_path);
    form.append("language", core.language);
    form.append("has_dockerfile", String(core.has_dockerfile));
    form.append("env_vars", JSON.stringify(envVars));

    const up = await axios.post(
      `${API_BASE}/projects/${projectId}/upload`,
      form,
      { headers: { Authorization: `Bearer ${token}`, ...form.getHeaders() } }
    );
    console.log("\nUpload result:");
    console.table(up.data);

    // cleanup
    fs.unlinkSync(tarName);

    // hint for resetting credentials
    console.log(
      "\nTo reset credentials, run:\n  rm ~/.benerspace/config.json\n"
    );
  });

export default init;
