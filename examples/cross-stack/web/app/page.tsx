"use client";
import { useState, type FormEvent } from "react";
export default function Page() {
  const [result, setResult] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = String(new FormData(event.currentTarget).get("name"));
    const response = await fetch("/api/items", {method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({name})});
    setResult(JSON.stringify(await response.json()));
  }
  return <main><h1>Catalog</h1><form onSubmit={submit}>
    <label htmlFor="name">Item name</label><input id="name" name="name" required maxLength={80}/>
    <button type="submit">Create item</button></form><output role="status">{result}</output></main>;
}
