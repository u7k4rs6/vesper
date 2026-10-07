import { redirect } from "next/navigation";

// The Store now lives on the demo page as scenario 02.
export default function StorePage() {
  redirect("/#checkout");
}
