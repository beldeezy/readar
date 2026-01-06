import { api } from "./client";

export type Me = {
  id: string;
  email: string;
};

export async function fetchMe(): Promise<Me> {
  const res = await api.get("/me");
  return res.data;
}

