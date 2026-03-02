import { useLocation, Link } from "react-router-dom";
import { useEffect } from "react";
import { House } from "lucide-react";

const NotFound = () => {
  const location = useLocation();

  useEffect(() => {
    console.error("404 Error: User attempted to access non-existent route:", location.pathname);
  }, [location.pathname]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background p-6">
      <div className="text-center">
        <h1 className="mb-4 text-6xl font-bold tracking-tight text-primary">404</h1>
        <h2 className="mb-2 text-2xl font-semibold text-foreground">Страница не найдена</h2>
        <p className="mb-8 text-muted-foreground">
          Возможно, она была удалена или вы ввели неправильный адрес.
        </p>
        <Link
          to="/"
          className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-primary px-6 py-2 text-sm font-medium text-primary-foreground shadow transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        >
          <House className="h-4 w-4" />
          На главную
        </Link>
      </div>
    </div>
  );
};

export default NotFound;
