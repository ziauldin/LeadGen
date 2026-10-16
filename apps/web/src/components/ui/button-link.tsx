import Link from "next/link";
import type { VariantProps } from "class-variance-authority";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** A real link (role="link") styled like a Button, for navigation actions. */
export function ButtonLink({
  variant,
  size,
  className,
  external = false,
  ...props
}: React.ComponentProps<typeof Link> &
  VariantProps<typeof buttonVariants> & { external?: boolean }) {
  const classes = cn(buttonVariants({ variant, size }), className);
  if (external) {
    const { href, children, ...rest } = props;
    return (
      <a
        href={String(href)}
        target="_blank"
        rel="noopener noreferrer"
        className={classes}
        {...(rest as React.ComponentProps<"a">)}
      >
        {children}
      </a>
    );
  }
  return <Link className={classes} {...props} />;
}
