"use client";
import { useEffect, useState, type FormEvent } from "react";
import { callOperation } from "../generated/operations";
export default function Page() {
  const [result, setResult] = useState("");
  const [ready, setReady] = useState(false);
  useEffect(() => setReady(true), []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = String(new FormData(event.currentTarget).get("name"));
    try {
      const result = await callOperation("urn:example:operation:create-item", {name});
      setResult(JSON.stringify(result.body));
    } catch {
      setResult("The item could not be created.");
    }
  }
  return <main><h1>Catalog</h1><form onSubmit={submit}>
    <label htmlFor="name">Item name</label><input id="name" name="name" required disabled={!ready}/>
    <button type="submit" disabled={!ready}>Create item</button></form><output role="status">{result}</output></main>;
}
