import { redirect } from "next/navigation";

// Signed-out visitors are sent on to /login by the middleware.
export default function HomePage() {
  redirect("/dashboard");
}
