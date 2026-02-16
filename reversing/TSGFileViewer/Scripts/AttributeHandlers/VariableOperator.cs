using Assets.Scripts;
using RWReader.RWStructs;
using System.IO;
using UnityEngine;

namespace AttributeHandlers
{
	public class VariableOperator : AttributeHandler
	{
		public enum Operator
		{
			ADD,
			SUBTRACT,
			SET,
			FLIP
		}

		public string m_targetName;
		public int m_variableHandle = -1;
		public Operator m_iOperator = Operator.ADD;
		public int m_iOperand = 1;

		public override void HandleAttributes(BinaryReader reader, SimGroup.AttrPacket attrPacket)
		{
			foreach (var attr in attrPacket.Attributes)
			{
				switch (attr.Index)
				{
					case 0:
						{
							reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
							m_targetName = reader.ReadNullTerminatedString();
							break;
						}

					case 1:
						{
							m_variableHandle = attr.Data.ToInt32BigEndian();
							break;
						}

					case 2:
						{
							m_iOperator = (Operator)attr.Data.ToInt32BigEndian();
							break;
						}

					case 3:
						{
							m_iOperand = attr.Data.ToInt32BigEndian();
							break;
						}
				}
			}
		}
	}
}