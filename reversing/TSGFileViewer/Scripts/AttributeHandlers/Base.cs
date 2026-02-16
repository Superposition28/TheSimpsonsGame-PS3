using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

namespace Assets.Scripts.AttributeHandlers
{
    public class Base : AttributeHandler
    {
	    public Guid128 InstanceID;

	    public uint m_flagsAndID = 0;

		public override void HandleAttributes(BinaryReader reader, SimGroup.AttrPacket attrPacket)
		{
			foreach (var attr in attrPacket.Attributes)
			{
				switch (attr.Index)
				{
					case 0:
						var val = reader.ReadUInt32BigEndian();
						if (val > 0)
						{
							m_flagsAndID |= 0x80000000;
						}
						else
						{
							m_flagsAndID &= 0x7FFFFFFF;
						}
						break;

					default:
						throw new NotImplementedException();
				}
			}
		}

	}
}
