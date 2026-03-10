import React from 'react';

interface SplitLayoutProps {
  leftPanel: React.ReactNode;
  rightPanel: React.ReactNode;
}

export function SplitLayout({ leftPanel, rightPanel }: SplitLayoutProps) {
  return (
    <div className="grid grid-cols-[40%_60%] h-screen">
      <div className="bg-gray-100 overflow-y-auto border-r border-gray-200">
        {leftPanel}
      </div>
      <div className="bg-white overflow-y-auto">
        {rightPanel}
      </div>
    </div>
  );
}
