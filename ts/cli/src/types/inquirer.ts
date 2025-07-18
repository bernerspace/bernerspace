import type { DistinctQuestion } from "inquirer";

export interface ProjectChoice {
  projectId: string;
}
export interface MetadataAnswers {
  current_path: string;
  language: string;
  has_dockerfile: boolean;
  env_vars: string;
}

export const projectChoiceQuestion: DistinctQuestion<ProjectChoice>[] = [
  {
    type: "list",
    name: "projectId",
    message: "Select a project or create new:",
    choices: []
  }
];

export const metadataQuestions: DistinctQuestion<MetadataAnswers>[] = [
  { type: "input", name: "current_path", message: "Current path:" },
  { type: "input", name: "language", message: "Language:" },
  { type: "confirm", name: "has_dockerfile", message: "Has Dockerfile?" },
  { type: "input", name: "env_vars", message: "Env vars (JSON):" }
];
export type MetadataQuestion = {
  name: string;
  default?: any;
};
