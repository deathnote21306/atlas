import { Toaster } from "react-hot-toast";
export { toast } from "react-hot-toast";

export function AppToaster() {
  return (
    <Toaster
      position="top-right"
      toastOptions={{
        duration: 4000,
        style: { fontSize: "0.875rem" },
        success: { iconTheme: { primary: "#16a34a", secondary: "#fff" } },
        error: { iconTheme: { primary: "#dc2626", secondary: "#fff" } },
      }}
    />
  );
}
