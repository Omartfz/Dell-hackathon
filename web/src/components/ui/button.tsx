import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-2 rounded-full font-semibold whitespace-nowrap transition-all outline-none select-none focus-visible:ring-3 focus-visible:ring-accent/25 disabled:pointer-events-none disabled:bg-disabled-bg disabled:text-disabled-text [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default: "bg-ink text-white hover:bg-[#262626]",
        ghost:
          "border border-border-input bg-white/60 text-ink hover:border-ink",
        quiet: "text-muted hover:text-ink",
        link: "text-accent underline-offset-4 hover:underline",
      },
      size: {
        default: "px-5 py-2.5 text-[15px]",
        lg: "px-6 py-3 text-[15px]",
        sm: "px-3.5 py-2 text-[13px]",
        icon: "size-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot.Root : "button"

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
