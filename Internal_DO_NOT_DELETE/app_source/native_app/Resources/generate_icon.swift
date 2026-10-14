import AppKit
import Foundation

let out = URL(fileURLWithPath: CommandLine.arguments[1])
let size = Int(CommandLine.arguments.dropFirst(2).first ?? "") ?? 1024
let canvas = NSSize(width: size, height: size)
let image = NSImage(size: canvas)

image.lockFocus()

let rect = NSRect(origin: .zero, size: canvas)
let inset = CGFloat(size) * 0.08
let cardRect = rect.insetBy(dx: inset, dy: inset)
let radius = CGFloat(size) * 0.22
let cardPath = NSBezierPath(roundedRect: cardRect, xRadius: radius, yRadius: radius)

NSColor.white.setFill()
cardPath.fill()

NSColor(calibratedWhite: 0.86, alpha: 1.0).setStroke()
cardPath.lineWidth = max(4, CGFloat(size) * 0.01)
cardPath.stroke()

let paragraph = NSMutableParagraphStyle()
paragraph.alignment = .center

let shadow = NSShadow()
shadow.shadowColor = NSColor(calibratedWhite: 0.0, alpha: 0.12)
shadow.shadowBlurRadius = CGFloat(size) * 0.025
shadow.shadowOffset = NSSize(width: 0, height: -CGFloat(size) * 0.01)

let dollarAttrs: [NSAttributedString.Key: Any] = [
    .font: NSFont.systemFont(ofSize: CGFloat(size) * 0.56, weight: .black),
    .foregroundColor: NSColor(calibratedRed: 0.05, green: 0.25, blue: 0.18, alpha: 1.0),
    .paragraphStyle: paragraph,
    .shadow: shadow,
]

let dollar = NSString(string: "$")
let textSize = dollar.size(withAttributes: dollarAttrs)
let textRect = NSRect(
    x: cardRect.midX - textSize.width * 0.5,
    y: cardRect.midY - textSize.height * 0.52,
    width: textSize.width,
    height: textSize.height
)
dollar.draw(in: textRect, withAttributes: dollarAttrs)

image.unlockFocus()

guard let tiff = image.tiffRepresentation,
      let rep = NSBitmapImageRep(data: tiff),
      let png = rep.representation(using: .png, properties: [:]) else {
    exit(1)
}

try png.write(to: out)
