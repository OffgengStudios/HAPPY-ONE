"use client";

import { Eye, EyeOff } from "lucide-react";
import { InputHTMLAttributes, useEffect, useId, useState } from "react";

type PasswordInputProps = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "type"
> & {
  visibilityDisabled?: boolean;
};

export function PasswordInput({
  id,
  className = "field",
  value,
  disabled,
  visibilityDisabled = false,
  ...props
}: PasswordInputProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (value === "") setVisible(false);
  }, [value]);
  const action = visible ? "Hide password" : "Show password";
  return (
    <div className="relative">
      <input
        {...props}
        id={inputId}
        className={className + " pr-12"}
        type={visible ? "text" : "password"}
        value={value}
        disabled={disabled}
      />
      <button
        type="button"
        aria-label={action}
        title={action}
        aria-controls={inputId}
        aria-pressed={visible}
        disabled={disabled || visibilityDisabled}
        onClick={() => setVisible((previous) => !previous)}
        className="absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-r-md text-muted hover:text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
      >
        {visible ? (
          <EyeOff aria-hidden="true" className="h-4 w-4" />
        ) : (
          <Eye aria-hidden="true" className="h-4 w-4" />
        )}
      </button>
    </div>
  );
}
