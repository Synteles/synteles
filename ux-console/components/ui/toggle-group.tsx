'use client'

import * as ToggleGroupPrimitive from '@radix-ui/react-toggle-group'
import { cn } from '@/lib/utils'

const ToggleGroup = ({
  className,
  ...props
}: React.ComponentProps<typeof ToggleGroupPrimitive.Root>) => (
  <ToggleGroupPrimitive.Root
    className={cn(
      'inline-flex items-center rounded-lg border border-border bg-surface p-0.5 gap-0.5',
      className,
    )}
    {...props}
  />
)

const ToggleGroupItem = ({
  className,
  children,
  ...props
}: React.ComponentProps<typeof ToggleGroupPrimitive.Item>) => (
  <ToggleGroupPrimitive.Item
    className={cn(
      'inline-flex items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium text-muted',
      'transition-all select-none outline-none',
      'hover:text-foreground-2',
      'data-[state=on]:bg-card data-[state=on]:text-foreground data-[state=on]:shadow-sm data-[state=on]:border data-[state=on]:border-border',
      'focus-visible:ring-2 focus-visible:ring-accent/40',
      className,
    )}
    {...props}
  >
    {children}
  </ToggleGroupPrimitive.Item>
)

export { ToggleGroup, ToggleGroupItem }
