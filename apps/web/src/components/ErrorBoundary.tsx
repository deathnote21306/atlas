import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-ink-950 px-4">
          <div className="w-full max-w-md rounded-[10px] border border-[#21262d] bg-[#161b22] p-8 text-center">
            <h1 className="text-lg font-semibold text-ink-100">
              Something went wrong
            </h1>
            <p className="mt-2 text-sm text-ink-400">
              {this.state.error?.message ?? "An unexpected error occurred."}
            </p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="mt-6 rounded bg-atlas-600 px-4 py-2 text-sm font-medium text-white hover:bg-atlas-700"
            >
              Reload
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
