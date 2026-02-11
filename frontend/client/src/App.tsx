import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import NotFound from "@/pages/NotFound";
import { Route, Switch } from "wouter";
import ErrorBoundary from "./components/ErrorBoundary";
import { ThemeProvider } from "./contexts/ThemeContext";
import DemoGallery from "./pages/DemoGallery";
import DemoPlayer from "./pages/DemoPlayer";
import Landing from "./pages/Landing";
import Home from "./pages/Home";
import ShareView from "./pages/ShareView";
import PPTPlayer from "./pages/PPTPlayer";
import Knowledge from "./pages/Knowledge";

function Router() {
  return (
    <Switch>
      <Route path={"/"} component={Landing} />
      <Route path="/demos" component={DemoGallery} />
      <Route path="/demos/:name" component={DemoPlayer} />
      <Route path="/chat" component={Home} />
      <Route path="/chat/:conversationId" component={Home} />
      <Route path="/knowledge-base" component={Knowledge} />
      <Route path="/share/:shareId" component={ShareView} />
      <Route path="/play/:id" component={PPTPlayer} />
      <Route path={"/404"} component={NotFound} />
      <Route component={NotFound} />
    </Switch>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider defaultTheme="light" switchable>
        <TooltipProvider>
          <Toaster />
          <Router />
        </TooltipProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
